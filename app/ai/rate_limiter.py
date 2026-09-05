import asyncio
import logging
import random
import time
from collections import deque
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter with request queueing for strict RPM compliance.
    Ensures that NVIDIA NIM's 40 requests/minute limit is never exceeded.
    Configured by default to 38 RPM to maintain a safe buffer against network jitter.
    """

    def __init__(self, max_requests: int = 38, time_window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.time_window_seconds = time_window_seconds
        self.timestamps = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire a slot to make an API request.
        If the number of requests in the current sliding window has reached max_requests,
        the caller asynchronously sleeps until an older request drops out of the window.
        """
        while True:
            async with self._lock:
                now = time.monotonic()

                # Evict timestamps older than the sliding window
                while self.timestamps and (now - self.timestamps[0]) >= self.time_window_seconds:
                    self.timestamps.popleft()

                # If we have available capacity in the current window
                if len(self.timestamps) < self.max_requests:
                    self.timestamps.append(now)
                    return

                # Window is full; calculate sleep duration until the oldest request expires
                oldest = self.timestamps[0]
                wait_time = (oldest + self.time_window_seconds) - now + 0.1  # 100ms safety margin

            logger.info(
                f"[RateLimiter] Osiągnięto limit {self.max_requests} req/{self.time_window_seconds}s. "
                f"Oczekiwanie {wait_time:.2f}s przed wysłaniem kolejnego zapytania do NVIDIA NIM."
            )
            await asyncio.sleep(max(wait_time, 0.1))

    def current_usage(self) -> int:
        """Return the number of requests executed within the current active window."""
        now = time.monotonic()
        while self.timestamps and (now - self.timestamps[0]) >= self.time_window_seconds:
            self.timestamps.popleft()
        return len(self.timestamps)


# Global singleton instance for the entire application
nim_rate_limiter = RateLimiter(max_requests=38, time_window_seconds=60.0)


async def execute_with_retry(
    func: Callable,
    *args,
    max_retries: int = 4,
    initial_backoff: float = 2.0,
    rate_limiter: Optional[RateLimiter] = None,
    **kwargs
):
    """
    Executes an async function guarded by the rate limiter with exponential backoff
    and jitter. Specifically handles HTTP 429 Too Many Requests and transient network errors.
    """
    limiter = rate_limiter or nim_rate_limiter
    backoff = initial_backoff

    for attempt in range(1, max_retries + 1):
        # Acquire rate limiter slot before each attempt
        await limiter.acquire()

        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            is_429 = (status_code == 429) or ("429" in str(exc))
            is_server_error = status_code in (500, 502, 503, 504) if status_code else False

            if attempt == max_retries:
                logger.error(f"[Retry] Wszystkie {max_retries} prób zakończone niepowodzeniem: {exc}")
                raise

            # Calculate backoff with jitter
            jitter = random.uniform(0.5, 1.5)
            wait_time = (backoff * jitter) if not is_429 else (backoff * 2.0 * jitter)

            # Check if exception has retry-after header
            response = getattr(exc, "response", None)
            if response and hasattr(response, "headers"):
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait_time = max(wait_time, float(retry_after) + 1.0)

            logger.warning(
                f"[Retry] Próba {attempt}/{max_retries} nie powiodła się ({exc}). "
                f"Ponawiam za {wait_time:.2f}s..."
            )
            await asyncio.sleep(wait_time)
            backoff *= 2.0
