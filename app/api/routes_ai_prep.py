import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.database.repository import LessonRepository
from app.api.schemas import (
    ExternalAIPart,
    ExternalAIPrepRequest,
    ExternalAIPrepResponse,
)
from app.ai.chunking import format_external_ai_parts
from app.exports.ai_bundle import (
    format_all_data_bundle,
    format_prompt_with_transcription,
    generate_analytical_prompt,
)

router = APIRouter(prefix="/api/lessons", tags=["ai_prep"])


@router.get("/{lesson_id}/ai-prep", response_model=ExternalAIPrepResponse)
async def get_material_for_external_ai(
    lesson_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve external AI preparation package (prompt + full transcription)."""
    return await _build_external_ai_response(lesson_id, ExternalAIPrepRequest(), db)


@router.post("/{lesson_id}/ai-prep", response_model=ExternalAIPrepResponse)
async def prepare_material_for_external_ai(
    lesson_id: str,
    req: ExternalAIPrepRequest = ExternalAIPrepRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    Prepares and formats lesson content specifically for external LLMs
    (ChatGPT, Claude, Gemini), generating both full transcription and analytical prompt.
    """
    return await _build_external_ai_response(lesson_id, req, db)


async def _build_external_ai_response(
    lesson_id: str,
    req: ExternalAIPrepRequest,
    db: AsyncSession
) -> ExternalAIPrepResponse:
    repo = LessonRepository(db)
    lesson = await repo.get_by_id(lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono lekcji.")

    # Extract topic from notes if present
    topic = "Lekcja"
    if lesson.notes:
        topic_match = re.search(r'#\s*Temat(?: lekcji)?:\s*([^\n\r]+)', lesson.notes, re.IGNORECASE)
        if topic_match:
            topic = topic_match.group(1).strip()
    if topic == "Lekcja" and lesson.subject:
        topic = lesson.subject

    # Build specialized analytical prompt
    analytical_prompt = generate_analytical_prompt(
        subject=lesson.subject,
        lesson_date=lesson.lesson_date,
        topic=topic
    )
    if req.custom_prompt:
        analytical_prompt = f"{req.custom_prompt}\n\n" + analytical_prompt

    transcription = lesson.transcription or "Brak transkrypcji."
    combined_text = (
        f"{analytical_prompt}\n\n"
        f"--- POCZĄTEK TRANSKRYPCJI LEKCJI ---\n\n"
        f"{transcription}\n\n"
        f"--- KONIEC TRANSKRYPCJI LEKCJI ---"
    )

    c_type = req.content_type.lower()
    if c_type in ("full_transcription", "transcription"):
        raw_text = transcription
    elif c_type in ("combined", "prompt_transcription"):
        raw_text = combined_text
    elif c_type == "summary":
        raw_text = lesson.summary or "Brak podsumowania."
    elif c_type == "note":
        raw_text = lesson.notes or "Brak notatki."
    elif c_type == "all_data":
        raw_text = format_all_data_bundle(
            topic=topic,
            subject=lesson.subject or "Nieokreślony",
            lesson_date=lesson.lesson_date,
            notes=lesson.notes,
            summary=lesson.summary,
            events=lesson.detected_events,
            transcription=lesson.transcription
        )
    else:
        # Default is the dedicated analytical prompt
        raw_text = analytical_prompt

    # Parts are ONLY generated if explicitly requested via split_parts=True
    parts_list: List[ExternalAIPart] = []
    if req.split_parts:
        formatted_chunks = format_external_ai_parts(raw_text, max_chars_per_part=req.max_chars_per_part)
        tot = len(formatted_chunks)
        for idx, part_str in enumerate(formatted_chunks, start=1):
            parts_list.append(
                ExternalAIPart(
                    part_number=idx,
                    total_parts=tot,
                    header=f"Część {idx}/{tot}",
                    content=part_str
                )
            )

    return ExternalAIPrepResponse(
        content_type=c_type,
        full_text=raw_text,
        parts=parts_list,
        analytical_prompt=analytical_prompt,
        transcription=transcription,
        combined_text=combined_text,
        subject=lesson.subject,
        lesson_date=lesson.lesson_date,
        topic=topic
    )
