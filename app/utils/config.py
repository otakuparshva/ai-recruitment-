import os
import logging
from typing import Optional, List
from pydantic import BaseModel, EmailStr, AnyUrl, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    # Application Config
    APP_NAME: str = "AI Recruitment System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database Configuration
    DATABASE_URL: str  # ✅ Added to match .env
    MONGO_URI: str
    MONGO_DB_NAME: str = "recruitment_db"
    MONGO_MAX_POOL_SIZE: int = 100
    MONGO_TIMEOUT_MS: int = 5000

    # AWS Configuration
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str
    S3_PRESIGNED_EXPIRE: int = 3600  # 1 hour

    # Email Configuration
    SMTP_SERVER: str
    SMTP_PORT: int = 587
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    EMAIL_FROM: EmailStr
    EMAIL_FROM_NAME: str = "Recruitment System"

    # AI Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    HF_API_TOKEN: Optional[str] = None
    HF_MODEL: Optional[str] = None
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Security Configuration
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"  # ✅ Added to match .env
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    PASSWORD_RESET_TIMEOUT: int = 3600  # 1 hour

    # File Uploads
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_FILE_TYPES: List[str] = ["pdf", "docx", "png", "jpg", "jpeg"]

    # OCR Configuration
    TESSERACT_PATH: Optional[str] = None

    # Additional Configurations from .env
    SCORE_THRESHOLD: int = 65  # ✅ Added to match .env
    DEFAULT_QUESTIONS: int = 15  # ✅ Added to match .env

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @field_validator("MONGO_URI")
    def validate_mongo_uri(cls, v):
        if not v.startswith("mongodb://"):
            raise ValueError("Invalid MongoDB URI format")
        return v

    @field_validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        v = v.upper()
        if v not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("Invalid log level")
        return v

    @field_validator("ENVIRONMENT")
    def validate_environment(cls, v):
        v = v.lower()
        if v not in ["development", "testing", "production"]:
            raise ValueError("Invalid environment")
        return v


def validate_config():
    """Validate critical configuration at startup"""
    errors = []
    required = {
        "DATABASE_URL": "PostgreSQL database connection string",
        "MONGO_URI": "MongoDB connection string",
        "AWS_ACCESS_KEY_ID": "AWS access key",
        "AWS_SECRET_ACCESS_KEY": "AWS secret key",
        "SMTP_SERVER": "SMTP server address",
        "SECRET_KEY": "Application secret key",
    }

    for var, desc in required.items():
        if not os.getenv(var):
            errors.append(f"Missing required config: {var} ({desc})")

    if errors:
        raise RuntimeError("\n".join(errors))


try:
    # Validate configuration on import
    validate_config()
    settings = Settings()
    logger.info("Configuration loaded successfully")
except Exception as e:
    logger.critical(f"Configuration validation failed: {str(e)}")
    raise

__all__ = ["settings"]
