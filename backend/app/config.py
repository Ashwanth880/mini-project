from pathlib import Path
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    APP_NAME: str = "One-Click Attendance System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    SECRET_KEY: str = "super-secret-key-for-one-click-attendance-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'attendance.db'}"

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = "*"

    # Storage paths
    FACES_DIR: Path = BASE_DIR.parent / "data" / "faces"
    ATTENDANCE_PHOTOS_DIR: Path = BASE_DIR.parent / "data" / "attendance_photos"
    CV_MODELS_DIR: Path = BASE_DIR.parent / "data" / "models"

    # Computer Vision Settings
    FACE_MATCH_THRESHOLD: float = 0.60
    MIN_FACE_CONFIDENCE: float = 0.70

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """
        Returns list of allowed origins.
        Note: When allow_credentials=True, browsers forbid wildcard '*' as an origin.
        We provide trusted local origins by default when wildcard is configured.
        """
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if self.CORS_ORIGINS == "*":
            return [
                "http://localhost:8000",
                "http://127.0.0.1:8000",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5500",
                "http://127.0.0.1:5500",
                "http://localhost:8080",
                "http://127.0.0.1:8080",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def validate_security_settings(self) -> None:
        """Enforces security rules for production environments."""
        is_prod = self.APP_ENV.lower() in ("production", "prod")
        insecure_keys = {
            "super-secret-key-for-one-click-attendance-2026",
            "dev-secret-key-change-in-production",
            "secret",
            "changeme",
            "password",
        }

        if is_prod:
            if self.SECRET_KEY in insecure_keys:
                raise RuntimeError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: Default development SECRET_KEY "
                    "cannot be used in production. Set a secure, random SECRET_KEY in .env."
                )
            if len(self.SECRET_KEY) < 32:
                raise RuntimeError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY must be at least 32 characters long in production."
                )

    def setup_directories(self) -> None:
        """Ensure necessary data and upload directories exist."""
        self.FACES_DIR.mkdir(parents=True, exist_ok=True)
        self.ATTENDANCE_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
        self.CV_MODELS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.validate_security_settings()

