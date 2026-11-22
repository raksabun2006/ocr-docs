"""
Centralized Configuration Module
Khmer Government Document Intelligence System

Manages all environment configurations, OCR settings, file upload constraints,
and security policies without hardcoding secrets or internal paths in business logic.
"""

import os
from pathlib import Path
from typing import List, Set
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings:
    """Application and OCR settings."""

    # Core Application
    APP_NAME: str = os.getenv("APP_NAME", "Khmer Government Document Intelligence System")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_DEBUG: bool = os.getenv("APP_DEBUG", "true").lower() in ("true", "1", "yes")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "cambodia_gov_doc_secret_key_change_in_production_min_32_chars")

    # Tesseract OCR Configuration (Windows 11)
    TESSERACT_CMD: str = os.getenv(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
    TESSDATA_DIR: str = os.getenv(
        "TESSDATA_DIR",
        r"C:\Users\TUF\tesseract-data"
    )
    OCR_DEFAULT_LANGUAGES: str = os.getenv("OCR_DEFAULT_LANGUAGES", "khm+eng")
    OCR_FALLBACK_LANGUAGES: str = os.getenv("OCR_FALLBACK_LANGUAGES", "eng")

    # File Storage & Upload Constraints
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
    MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    UPLOAD_DIR: Path = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads/documents")
    ALLOWED_EXTENSIONS: Set[str] = {
        ext.strip().lower()
        for ext in os.getenv("ALLOWED_EXTENSIONS", ".jpg,.jpeg,.png,.pdf").split(",")
    }
    ALLOWED_MIME_TYPES: Set[str] = {
        "image/jpeg",
        "image/png",
        "application/pdf",
    }

    # Database Configuration (PostgreSQL + SQLAlchemy)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/khmer_gov_docs"
    )
    DB_FALLBACK_SQLITE: bool = os.getenv("DB_FALLBACK_SQLITE", "true").lower() in ("true", "1", "yes")
    SQLITE_URL: str = os.getenv("SQLITE_URL", f"sqlite:///{BASE_DIR / 'khmer_gov_docs.db'}")

    # Security & Confidence Thresholds
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MASK_SENSITIVE_LOGS: bool = os.getenv("MASK_SENSITIVE_LOGS", "true").lower() in ("true", "1", "yes")
    CONFIDENCE_THRESHOLD_HIGH: float = float(os.getenv("CONFIDENCE_THRESHOLD_HIGH", "80.0"))
    CONFIDENCE_THRESHOLD_MEDIUM: float = float(os.getenv("CONFIDENCE_THRESHOLD_MEDIUM", "50.0"))

    # JWT & Authentication Policies
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", "cambodia_gov_doc_secret_key_change_in_production_min_32_chars"))
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    MAX_FAILED_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
    ACCOUNT_LOCKOUT_MINUTES: int = int(os.getenv("ACCOUNT_LOCKOUT_MINUTES", "15"))

    # AI & Ollama OCR Vision Configuration
    OLLAMA_ENABLED: bool = os.getenv("OLLAMA_ENABLED", "false").lower() in ("true", "1", "yes")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5-vl")
    OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30"))
    DEFAULT_OCR_PROVIDER: str = os.getenv("DEFAULT_OCR_PROVIDER", "TESSERACT")

    def get_clean_tessdata_dir(self) -> str:
        """
        Return normalized tessdata directory path for Windows without enclosing quotes
        or trailing backslashes that cause Tesseract command-line path concatenation errors.
        """
        raw_path = self.TESSDATA_DIR.strip().strip('"').strip("'")
        # Normalize slashes and remove trailing slash
        normalized = os.path.normpath(raw_path)
        return normalized

    def setup_ocr_environment(self) -> None:
        """
        Configures Tesseract environment variables and pytesseract settings.
        Ensures TESSDATA_PREFIX is set globally so all sub-processes find language models.
        """
        clean_dir = self.get_clean_tessdata_dir()
        if clean_dir and os.path.isdir(clean_dir):
            os.environ["TESSDATA_PREFIX"] = clean_dir

        try:
            import pytesseract
            if os.path.exists(self.TESSERACT_CMD):
                pytesseract.pytesseract.tesseract_cmd = self.TESSERACT_CMD
        except ImportError:
            pass


settings = Settings()
# Execute initial OCR environment setup
settings.setup_ocr_environment()
