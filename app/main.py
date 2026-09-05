from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database.session import init_db
from app.api.routes_upload import router as upload_router
from app.api.routes_lessons import router as lessons_router
from app.api.routes_settings import router as settings_router
from app.api.routes_calendar import router as calendar_router
from app.api.routes_export import router as export_router
from app.api.routes_ai_prep import router as ai_prep_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("notely")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure directories and initialize DB
    settings.ensure_directories()
    await init_db()
    logger.info("Notely application started successfully.")
    yield
    # Shutdown
    logger.info("Notely application shutting down.")


app = FastAPI(
    title="Notely API",
    description="Automatyczne przetwarzanie nagrań lekcji na uporządkowane notatki",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include API Routers
app.include_router(upload_router)
app.include_router(lessons_router)
app.include_router(settings_router)
app.include_router(calendar_router)
app.include_router(export_router)
app.include_router(ai_prep_router)


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serve the main user interface."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "version": "1.0.0",
            "default_engine": settings.TRANSCRIPTION_ENGINE,
            "default_model": settings.WHISPER_MODEL
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestrators."""
    return {
        "status": "healthy",
        "env": settings.APP_ENV,
        "engine": settings.TRANSCRIPTION_ENGINE,
        "nim_model": settings.NVIDIA_NIM_MODEL
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global error handler providing user-friendly JSON messages without tracebacks."""
    logger.error(f"Nieobsłużony wyjątek dla {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Wewnętrzny błąd serwera: {str(exc)}"}
    )
