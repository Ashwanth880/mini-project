import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure backend directory is in sys.path regardless of execution working directory
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.config import settings
from app.database import init_db
from app.api import api_router
from app.api.auth import router as auth_router
from app.api.students import router as students_router
from app.api.attendance import router as attendance_router
from app.services.face_service import (
    FaceEnrollmentError,
    StudentNotFoundError,
    NoFaceDetectedError,
    MultipleFacesDetectedError,
    ImageQualityError,
    InvalidImageError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("one-click-attendance")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: setups storage directories and database tables."""
    logger.info("Initializing storage directories...")
    settings.setup_directories()

    logger.info("Initializing database tables...")
    init_db()

    logger.info(f"'{settings.APP_NAME}' started successfully in {settings.APP_ENV} mode.")
    yield
    logger.info("Shutting down application...")


app = FastAPI(
    title=settings.APP_NAME,
    description="One-Click Attendance System for Schools and Colleges Using Computer Vision",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Global Face Enrollment Exception Handlers
@app.exception_handler(FaceEnrollmentError)
async def face_enrollment_exception_handler(request: Request, exc: FaceEnrollmentError):
    if isinstance(exc, StudentNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
        message = "Student not found"
    elif isinstance(exc, NoFaceDetectedError):
        status_code = status.HTTP_400_BAD_REQUEST
        message = "No face detected"
    elif isinstance(exc, MultipleFacesDetectedError):
        status_code = status.HTTP_400_BAD_REQUEST
        message = "Multiple faces detected"
    elif isinstance(exc, ImageQualityError):
        status_code = status.HTTP_400_BAD_REQUEST
        message = "Image quality insufficient"
    elif isinstance(exc, InvalidImageError):
        status_code = status.HTTP_400_BAD_REQUEST
        message = f"Invalid image file: {str(exc)}"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        message = "Face enrollment failed"

    logger.warning(f"Face enrollment pipeline handled exception: {message} ({exc})")
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "detail": message,
            "error": str(exc),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message = detail if isinstance(detail, str) else str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": message,
            "detail": detail,
        },
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    """
    Prevents raw tracebacks, database schema details, or sensitive internals
    from leaking to external clients in production.
    """
    logger.exception(f"Unhandled server error on {request.method} {request.url.path}: {exc}")
    detail = str(exc) if settings.DEBUG else "An internal server error occurred. Please contact the administrator."
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": detail,
        },
    )


# CORS middleware with explicit origins and localhost regex for secure local dev credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$" if settings.CORS_ORIGINS == "*" else None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include direct /auth router for explicit root endpoints:
# POST /auth/login, POST /auth/register, GET /auth/me
app.include_router(auth_router)

# Include direct /students router for root endpoints:
# POST /students/{student_id}/face, GET /students/{student_id}/face
app.include_router(students_router)

# Include direct /attendance router for root endpoints:
# POST /attendance/analyze, POST /attendance/confirm
app.include_router(attendance_router)

# Include API Router (/api/v1)
app.include_router(api_router)

# Mount frontend directory for easy single-host preview
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    if (FRONTEND_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

# Mount faces and attendance photos storage directory for portraits and previews
settings.setup_directories()
if settings.FACES_DIR.exists():
    app.mount("/faces", StaticFiles(directory=str(settings.FACES_DIR)), name="faces")
if settings.ATTENDANCE_PHOTOS_DIR.exists():
    app.mount("/attendance_photos", StaticFiles(directory=str(settings.ATTENDANCE_PHOTOS_DIR)), name="attendance_photos")


@app.get("/", tags=["Health & Status"])
def root(request: Request):
    """Root health and information endpoint; serves frontend for browser requests."""
    accept = request.headers.get("accept", "")
    index_file = FRONTEND_DIR / "index.html"
    # Serve HTML for browser requests (which include text/html or */*)
    if index_file.exists() and ("text/html" in accept or "*/*" in accept or not accept):
        return FileResponse(
            index_file,
            media_type="text/html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {
        "app_name": settings.APP_NAME,
        "status": "online",
        "version": "0.1.0",
        "docs_url": "/docs",
        "api_v1": "/api/v1",
        "frontend_preview": "/static/index.html",
        "auth_endpoints": {
            "login": "/auth/login",
            "register": "/auth/register",
            "me": "/auth/me",
        },
    }


@app.get("/health", tags=["Health & Status"])
def health_check():
    """Standard health check."""
    return {"status": "healthy"}
