from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.database.repository import SettingsRepository
from app.api.schemas import UserSettingsSchema, UserSettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=UserSettingsSchema)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Retrieve current persistent application settings."""
    repo = SettingsRepository(db)
    s = await repo.get_or_create_settings()
    # Mask API key if set
    masked_key = (s.nvidia_api_key[:4] + "..." + s.nvidia_api_key[-4:]) if s.nvidia_api_key and len(s.nvidia_api_key) > 8 else (s.nvidia_api_key or "")
    return UserSettingsSchema(
        transcription_engine=s.transcription_engine,
        whisper_model=s.whisper_model,
        whisper_device=s.whisper_device,
        whisper_compute_type=s.whisper_compute_type,
        whisper_language=s.whisper_language,
        nvidia_nim_model=s.nvidia_nim_model,
        nvidia_temperature=s.nvidia_temperature,
        nvidia_api_key=masked_key,
        nvidia_base_url=s.nvidia_base_url,
        delete_source_after_processing=s.delete_source_after_processing,
        google_calendar_auto_add=s.google_calendar_auto_add,
        preferred_export_format=s.preferred_export_format
    )


@router.post("", response_model=UserSettingsSchema)
async def update_settings(
    update_data: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update and persist global default settings."""
    repo = SettingsRepository(db)

    # Don't overwrite key if user didn't change masked key
    payload = update_data.model_dump(exclude_unset=True)
    if payload.get("nvidia_api_key") and "..." in payload["nvidia_api_key"]:
        del payload["nvidia_api_key"]

    updated = await repo.update_settings(**payload)
    masked_key = (updated.nvidia_api_key[:4] + "..." + updated.nvidia_api_key[-4:]) if updated.nvidia_api_key and len(updated.nvidia_api_key) > 8 else (updated.nvidia_api_key or "")

    return UserSettingsSchema(
        transcription_engine=updated.transcription_engine,
        whisper_model=updated.whisper_model,
        whisper_device=updated.whisper_device,
        whisper_compute_type=updated.whisper_compute_type,
        whisper_language=updated.whisper_language,
        nvidia_nim_model=updated.nvidia_nim_model,
        nvidia_temperature=updated.nvidia_temperature,
        nvidia_api_key=masked_key,
        nvidia_base_url=updated.nvidia_base_url,
        delete_source_after_processing=updated.delete_source_after_processing,
        google_calendar_auto_add=updated.google_calendar_auto_add,
        preferred_export_format=updated.preferred_export_format
    )
