import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings
from app.ai.base import AIProvider, DetectedEvent, LessonAnalysisResult
from app.ai.chunking import chunk_plain_text, chunk_segments
from app.ai.date_resolver import resolve_relative_date
from app.ai.prompts import (
    CHUNK_ANALYSIS_PROMPT,
    EVENT_EXTRACTION_PROMPT,
    FINAL_NOTE_PROMPT,
    LESSON_SYNTHESIS_PROMPT,
    SYSTEM_PROMPT_ANALYST,
)
from app.ai.rate_limiter import execute_with_retry, nim_rate_limiter
from app.transcription.base import TranscriptionResult

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """Exception for AI API and analysis errors."""
    pass


class NvidiaNimProvider(AIProvider):
    """
    AI Provider integrating with NVIDIA NIM API.
    Enforces strict 40 RPM global rate limiting, sliding window, and exponential backoff.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2
    ):
        self.api_key = api_key or settings.NVIDIA_API_KEY
        self.model = model or settings.NVIDIA_NIM_MODEL
        self.base_url = (base_url or settings.NVIDIA_BASE_URL).rstrip("/")
        self.temperature = temperature
        self.timeout = settings.NVIDIA_REQUEST_TIMEOUT_SECONDS

    async def _call_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> str:
        """
        Calls NVIDIA NIM chat completions endpoint with rate limiting and exponential backoff.
        """
        if not self.api_key or self.api_key.strip() in ("", "your_nvidia_api_key_here"):
            raise AIProviderError(
                "Brak klucza NVIDIA_API_KEY. Skonfiguruj klucz API w pliku .env lub w Ustawieniach aplikacji."
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": 4096
        }

        async def _request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 401:
                    raise AIProviderError("Nieprawidłowy klucz NVIDIA API (HTTP 401 Unauthorized).")
                if response.status_code == 429:
                    raise httpx.HTTPStatusError("HTTP 429 Too Many Requests", request=response.request, response=response)
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise AIProviderError("NVIDIA NIM zwróciło pustą odpowiedź.")
                return choices[0].get("message", {}).get("content", "").strip()

        return await execute_with_retry(
            _request,
            max_retries=settings.NVIDIA_MAX_RETRIES,
            initial_backoff=settings.NVIDIA_INITIAL_BACKOFF_SECONDS,
            rate_limiter=nim_rate_limiter
        )

    def _extract_json_from_response(self, text: str) -> Dict[str, Any]:
        """
        Robust JSON extraction handling markdown blocks, backticks, and partial JSON.
        """
        text = text.strip()

        # 1. Try markdown code block
        code_block = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if code_block:
            json_str = code_block.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 2. Try whole text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 3. Try to find the outermost { ... }
        match = re.search(r'(\{[\s\S]*\})', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Fallback empty structure
        logger.warning(f"Nie udało się sparsować odpowiedzi AI jako JSON: {text[:200]}...")
        return {"events": []}

    async def _extract_events(
        self,
        transcript_text: str,
        lesson_date: Optional[str]
    ) -> List[DetectedEvent]:
        """Extracts structured events and resolves relative dates."""
        prompt = EVENT_EXTRACTION_PROMPT.format(text=transcript_text[:12000])
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_ANALYST},
            {"role": "user", "content": prompt}
        ]

        try:
            raw_response = await self._call_chat_completion(messages, temperature=0.1)
            parsed = self._extract_json_from_response(raw_response)
            events_data = parsed.get("events", [])
            if not isinstance(events_data, list):
                events_data = []

            results: List[DetectedEvent] = []
            for ev in events_data:
                if not isinstance(ev, dict):
                    continue

                raw_expr = ev.get("raw_date_expression") or ev.get("date")
                resolution = resolve_relative_date(raw_expr, base_lesson_date=lesson_date)

                final_date = resolution.resolved_date or ev.get("date")
                raw_conf = float(ev.get("confidence", 0.8))
                final_conf = max(0.1, min(1.0, raw_conf - resolution.confidence_penalty))

                results.append(
                    DetectedEvent(
                        type=str(ev.get("type", "other")),
                        title=str(ev.get("title", "Wydarzenie z lekcji")),
                        date=final_date,
                        raw_date_expression=raw_expr,
                        time=ev.get("time"),
                        description=str(ev.get("description", "")),
                        confidence=final_conf,
                        source_text=str(ev.get("source_text", "")),
                        is_date_calculated=resolution.is_calculated,
                        date_explanation=resolution.explanation
                    )
                )

            return results
        except Exception as e:
            logger.error(f"Błąd podczas ekstrakcji wydarzeń: {e}")
            return []

    async def analyze_lesson(
        self,
        transcription_result: TranscriptionResult,
        lesson_date: Optional[str] = None,
        given_subject: Optional[str] = None
    ) -> LessonAnalysisResult:
        full_text = transcription_result.text.strip()
        if not full_text:
            raise AIProviderError("Transkrypcja jest pusta — brak treści do analizy.")

        # Step 1: Chunking
        if transcription_result.segments:
            chunks = chunk_segments(transcription_result.segments, max_chunk_chars=5500)
        else:
            raw_parts = chunk_plain_text(full_text, max_chunk_chars=5500)
            from app.ai.chunking import TranscriptionChunk
            chunks = [
                TranscriptionChunk(
                    index=i + 1,
                    total=len(raw_parts),
                    start_time=0.0,
                    end_time=transcription_result.duration,
                    text=p
                )
                for i, p in enumerate(raw_parts)
            ]

        # Step 2: Intermediate Summaries (if multiple chunks)
        intermediate_summaries: List[str] = []
        if len(chunks) > 1:
            for chunk in chunks:
                prompt = CHUNK_ANALYSIS_PROMPT.format(
                    chunk_index=chunk.index,
                    total_chunks=chunk.total,
                    time_range=chunk.time_range_str,
                    chunk_text=chunk.text
                )
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT_ANALYST},
                    {"role": "user", "content": prompt}
                ]
                summary = await self._call_chat_completion(messages)
                intermediate_summaries.append(f"[Fragment {chunk.index}/{chunk.total} ({chunk.time_range_str})]\n{summary}")
            synthesis_input = "\n\n".join(intermediate_summaries)
        else:
            synthesis_input = chunks[0].text if chunks else full_text

        # Step 3: Event Extraction
        detected_events = await self._extract_events(full_text, lesson_date)

        # Step 4: Lesson Synthesis
        synthesis_prompt = LESSON_SYNTHESIS_PROMPT.format(
            intermediate_summaries=synthesis_input[:10000],
            subject=given_subject or "Nieokreślony",
            lesson_date=lesson_date or "Brak daty"
        )
        synthesis_messages = [
            {"role": "system", "content": SYSTEM_PROMPT_ANALYST},
            {"role": "user", "content": synthesis_prompt}
        ]
        synthesis_result = await self._call_chat_completion(synthesis_messages)

        # Step 5: Final Note Generation
        final_note_prompt = FINAL_NOTE_PROMPT.format(
            synthesis=synthesis_result,
            key_excerpts=full_text[:6000]
        )
        final_note_messages = [
            {"role": "system", "content": SYSTEM_PROMPT_ANALYST},
            {"role": "user", "content": final_note_prompt}
        ]
        final_notes = await self._call_chat_completion(final_note_messages)

        # Extract topic & subject from final note / synthesis
        topic_match = re.search(r'#\s*Temat(?: lekcji)?:\s*([^\n\r]+)', final_notes, re.IGNORECASE)
        topic = topic_match.group(1).strip() if topic_match else "Lekcja"

        final_subject = given_subject
        if not final_subject or final_subject.lower() in ("nieokreślony", "brak", ""):
            # Detect subject from text
            subj_match = re.search(r'(?:Przedmiot|Dyscyplina):\s*([^\n\r]+)', synthesis_result, re.IGNORECASE)
            final_subject = subj_match.group(1).strip() if subj_match else "Ogólny"

        return LessonAnalysisResult(
            subject=final_subject,
            topic=topic,
            summary=synthesis_result[:1000],
            notes=final_notes,
            events=detected_events
        )
