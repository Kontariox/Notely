from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.database.repository import LessonRepository
from app.services.audio import cleanup_file
from app.api.schemas import LessonListItem, LessonResponse, LessonStatusResponse

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("", response_model=List[LessonListItem])
async def list_lessons(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """List recent processed lessons."""
    repo = LessonRepository(db)
    lessons = await repo.list_recent(limit=limit)
    return [
        LessonListItem(
            id=l.id,
            created_at=l.created_at,
            lesson_date=l.lesson_date,
            subject=l.subject,
            original_filename=l.original_filename,
            duration=l.duration,
            status=l.status,
            progress_percent=l.progress_percent,
            current_stage=l.current_stage
        )
        for l in lessons
    ]


@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    lesson_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all details, transcription, and notes for a specific lesson."""
    repo = LessonRepository(db)
    lesson = await repo.get_by_id(lesson_id)
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono lekcji o podanym identyfikatorze."
        )

    return LessonResponse(
        id=lesson.id,
        created_at=lesson.created_at,
        lesson_date=lesson.lesson_date,
        subject=lesson.subject,
        original_filename=lesson.original_filename,
        duration=lesson.duration,
        transcription_engine=lesson.transcription_engine,
        transcription=lesson.transcription,
        segments=lesson.segments,
        summary=lesson.summary,
        notes=lesson.notes,
        detected_events=lesson.detected_events,
        status=lesson.status,
        progress_percent=lesson.progress_percent,
        current_stage=lesson.current_stage,
        error_message=lesson.error_message
    )


@router.get("/{lesson_id}/status", response_model=LessonStatusResponse)
async def get_lesson_status(
    lesson_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Check processing status and progress for polling."""
    repo = LessonRepository(db)
    lesson = await repo.get_by_id(lesson_id)
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono lekcji o podanym ID."
        )

    return LessonStatusResponse(
        id=lesson.id,
        status=lesson.status,
        progress_percent=lesson.progress_percent,
        current_stage=lesson.current_stage,
        error_message=lesson.error_message
    )


@router.delete("/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(
    lesson_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete lesson record and associated uploaded files."""
    repo = LessonRepository(db)
    lesson = await repo.get_by_id(lesson_id)
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono lekcji do usunięcia."
        )

    if lesson.file_path:
        cleanup_file(Path(lesson.file_path))

    await repo.delete_lesson(lesson_id)
    return None
