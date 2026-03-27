import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]
LOCAL_SUPABASE_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
CLOSET_UPLOAD_ALLOWED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
CLOSET_UPLOAD_MAX_FILE_SIZE = 15 * 1024 * 1024
CLOSET_UPLOAD_MAX_WIDTH = 8000
CLOSET_UPLOAD_MAX_HEIGHT = 8000
CLOSET_UPLOAD_INTENT_TTL_SECONDS = 15 * 60

load_dotenv(REPO_ROOT / ".env")
load_dotenv(API_ROOT / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    database_url: str
    supabase_url: str
    supabase_client_key: str
    supabase_auth_timeout_seconds: float
    minio_endpoint: str
    minio_console_url: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_region: str


def load_supabase_client_key() -> str:
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if publishable_key:
        return publishable_key

    return os.getenv("SUPABASE_ANON_KEY", "").strip()


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Tenue API"),
        environment=os.getenv("APP_ENV", os.getenv("TENUE_ENV", "development")),
        database_url=os.getenv("DATABASE_URL", LOCAL_SUPABASE_DATABASE_URL),
        supabase_url=os.getenv("SUPABASE_URL", "http://127.0.0.1:54321"),
        supabase_client_key=load_supabase_client_key(),
        supabase_auth_timeout_seconds=float(os.getenv("SUPABASE_AUTH_TIMEOUT_SECONDS", "10")),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://127.0.0.1:9000"),
        minio_console_url=os.getenv("MINIO_CONSOLE_URL", "http://127.0.0.1:9001"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        minio_bucket=os.getenv("MINIO_BUCKET", "tenue-dev"),
        minio_region=os.getenv("MINIO_REGION", "us-east-1"),
    )


settings = load_settings()
