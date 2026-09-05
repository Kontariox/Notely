import asyncio
import time
import pytest
from app.ai.rate_limiter import RateLimiter, execute_with_retry


@pytest.mark.asyncio
async def test_rate_limiter_throttling():
    # Limit to 3 requests per 0.4 seconds
    limiter = RateLimiter(max_requests=3, time_window_seconds=0.4)

    start_time = time.monotonic()
    # Acquire 3 slots immediately
    for _ in range(3):
        await limiter.acquire()

    assert limiter.current_usage() == 3

    # 4th request must be delayed until sliding window expires
    await limiter.acquire()
    elapsed = time.monotonic() - start_time

    assert elapsed >= 0.35
    assert limiter.current_usage() <= 3


@pytest.mark.asyncio
async def test_execute_with_retry_success():
    call_count = 0

    async def mock_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Transient 429 Too Many Requests")
        return "Success"

    limiter = RateLimiter(max_requests=10, time_window_seconds=1.0)
    result = await execute_with_retry(
        mock_call,
        max_retries=4,
        initial_backoff=0.05,
        rate_limiter=limiter
    )

    assert result == "Success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_execute_with_retry_exhausted():
    async def mock_failing_call():
        raise RuntimeError("Persistent network error")

    limiter = RateLimiter(max_requests=10, time_window_seconds=1.0)
    with pytest.raises(RuntimeError, match="Persistent network error"):
        await execute_with_retry(
            mock_failing_call,
            max_retries=2,
            initial_backoff=0.05,
            rate_limiter=limiter
        )
