from app.api.routes_upload import router as upload_router
from app.api.routes_lessons import router as lessons_router
from app.api.routes_settings import router as settings_router
from app.api.routes_calendar import router as calendar_router
from app.api.routes_export import router as export_router
from app.api.routes_ai_prep import router as ai_prep_router

__all__ = [
    "upload_router",
    "lessons_router",
    "settings_router",
    "calendar_router",
    "export_router",
    "ai_prep_router"
]
