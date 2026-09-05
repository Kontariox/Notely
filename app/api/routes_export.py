import json
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.database.repository import LessonRepository
from app.exports.srt_exporter import export_to_srt, export_to_vtt
from app.exports.docx_exporter import create_lesson_docx
from app.exports.ai_bundle import format_all_data_bundle

router = APIRouter(prefix="/api/lessons", tags=["export"])


@router.get("/{lesson_id}/export/transcription")
async def export_transcription(
    lesson_id: str,
    format: str = Query("txt", pattern="^(txt|md|json|srt|vtt)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports full raw transcription in TXT, Markdown, JSON, SRT, or WebVTT.
    Guaranteed to be available as long as transcription completed, independent of AI notes.
    """
    repo = LessonRepository(db)
    lesson = await repo.get_by_id(lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono lekcji.")

    text = lesson.transcription or ""
    filename_base = f"transkrypcja_{lesson.id[:8]}"

    if format == "txt":
        return Response(
            content=text,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.txt"'}
        )

    elif format == "md":
        md_content = f"# Transkrypcja: {lesson.original_filename}\n\nPrzedmiot: {lesson.subject} | Data: {lesson.lesson_date or 'Brak'}\n\n{text}"
        return Response(
            content=md_content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.md"'}
        )

    elif format == "json":
        json_data = {
            "lesson_id": lesson.id,
            "filename": lesson.original_filename,
            "duration": lesson.duration,
            "language": "pl",
            "transcription": text,
            "segments": lesson.segments
        }
        return Response(
            content=json.dumps(json_data, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.json"'}
        )

    elif format == "srt":
        srt_content = export_to_srt(lesson.segments)
        return Response(
            content=srt_content,
            media_type="application/x-subrip; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.srt"'}
        )

    elif format == "vtt":
        vtt_content = export_to_vtt(lesson.segments)
        return Response(
            content=vtt_content,
            media_type="text/vtt; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.vtt"'}
        )


@router.get("/{lesson_id}/export/note")
async def export_note(
    lesson_id: str,
    format: str = Query("md", pattern="^(md|txt|docx|json)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports generated structured note in Markdown, TXT, DOCX, or JSON.
    """
    repo = LessonRepository(db)
    lesson = await repo.get_by_id(lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono lekcji.")

    note_text = lesson.notes or "Brak wygenerowanej notatki."
    filename_base = f"notatka_{lesson.id[:8]}"

    if format == "md":
        return Response(
            content=note_text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.md"'}
        )

    elif format == "txt":
        return Response(
            content=note_text,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.txt"'}
        )

    elif format == "docx":
        docx_stream = create_lesson_docx(
            title=f"Notatka: {lesson.subject or 'Lekcja'}",
            subject=lesson.subject or "Nieokreślony",
            lesson_date=lesson.lesson_date,
            notes_markdown=note_text,
            events=lesson.detected_events
        )
        return StreamingResponse(
            docx_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.docx"'}
        )

    elif format == "json":
        json_data = {
            "lesson_id": lesson.id,
            "subject": lesson.subject,
            "lesson_date": lesson.lesson_date,
            "summary": lesson.summary,
            "notes": lesson.notes,
            "events": lesson.detected_events
        }
        return Response(
            content=json.dumps(json_data, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.json"'}
        )


@router.get("/{lesson_id}/export/all")
async def export_all_data(
    lesson_id: str,
    format: str = Query("md", pattern="^(md|txt|docx|json)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports combined comprehensive document (Topic + Notes + Summary + Events + Full Transcription).
    """
    repo = LessonRepository(db)
    lesson = await repo.get_by_id(lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono lekcji.")

    bundle_text = format_all_data_bundle(
        topic=lesson.subject or "Lekcja",
        subject=lesson.subject or "Nieokreślony",
        lesson_date=lesson.lesson_date,
        notes=lesson.notes,
        summary=lesson.summary,
        events=lesson.detected_events,
        transcription=lesson.transcription
    )
    filename_base = f"lekcja_pelny_pakiet_{lesson.id[:8]}"

    if format in ("md", "txt"):
        media = "text/markdown" if format == "md" else "text/plain"
        return Response(
            content=bundle_text,
            media_type=f"{media}; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.{format}"'}
        )

    elif format == "docx":
        docx_stream = create_lesson_docx(
            title=f"Kompletny pakiet: {lesson.subject or 'Lekcja'}",
            subject=lesson.subject or "Nieokreślony",
            lesson_date=lesson.lesson_date,
            notes_markdown=lesson.notes or "",
            events=lesson.detected_events,
            transcription=lesson.transcription
        )
        return StreamingResponse(
            docx_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.docx"'}
        )

    elif format == "json":
        json_data = {
            "lesson_id": lesson.id,
            "created_at": lesson.created_at.isoformat() if lesson.created_at else None,
            "subject": lesson.subject,
            "lesson_date": lesson.lesson_date,
            "filename": lesson.original_filename,
            "duration": lesson.duration,
            "transcription": lesson.transcription,
            "segments": lesson.segments,
            "summary": lesson.summary,
            "notes": lesson.notes,
            "detected_events": lesson.detected_events
        }
        return Response(
            content=json.dumps(json_data, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.json"'}
        )
