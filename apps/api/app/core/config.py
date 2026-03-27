import os
from dataclasses import dataclass

from app.core.db_target import load_project_env, resolve_database_target

CLOSET_UPLOAD_ALLOWED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
CLOSET_UPLOAD_MAX_FILE_SIZE = 15 * 1024 * 1024
CLOSET_UPLOAD_MAX_WIDTH = 8000
CLOSET_UPLOAD_MAX_HEIGHT = 8000
CLOSET_UPLOAD_INTENT_TTL_SECONDS = 15 * 60
DEFAULT_PHOTOROOM_BASE_URL = "https://sdk.photoroom.com/v1/segment"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

load_project_env()


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    database_target: str
    database_url: str
    database_source: str
    database_host: str | None
    supabase_url: str
    supabase_client_key: str
    supabase_auth_timeout_seconds: float
    minio_endpoint: str
    minio_console_url: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_region: str
    closet_media_download_ttl_seconds: int
    closet_thumbnail_max_edge: int
    closet_background_removal_provider: str
    photoroom_api_key: str
    photoroom_base_url: str
    photoroom_timeout_seconds: float
    closet_metadata_extraction_provider: str
    gemini_api_key: str
    gemini_base_url: str
    gemini_model: str
    gemini_timeout_seconds: float
    closet_metadata_extraction_max_edge: int


def load_supabase_client_key() -> str:
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if publishable_key:
        return publishable_key

    return os.getenv("SUPABASE_ANON_KEY", "").strip()


def load_settings() -> Settings:
    database_target = resolve_database_target()
    return Settings(
        app_name=os.getenv("APP_NAME", "Tenue API"),
        environment=os.getenv("APP_ENV", os.getenv("TENUE_ENV", "development")),
        database_target=database_target.target,
        database_url=database_target.database_url,
        database_source=database_target.source,
        database_host=database_target.host,
        supabase_url=os.getenv("SUPABASE_URL", "http://127.0.0.1:54321"),
        supabase_client_key=load_supabase_client_key(),
        supabase_auth_timeout_seconds=float(os.getenv("SUPABASE_AUTH_TIMEOUT_SECONDS", "10")),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://127.0.0.1:9000"),
        minio_console_url=os.getenv("MINIO_CONSOLE_URL", "http://127.0.0.1:9001"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        minio_bucket=os.getenv("MINIO_BUCKET", "tenue-dev"),
        minio_region=os.getenv("MINIO_REGION", "us-east-1"),
        closet_media_download_ttl_seconds=int(
            os.getenv("CLOSET_MEDIA_DOWNLOAD_TTL_SECONDS", "300")
        ),
        closet_thumbnail_max_edge=int(os.getenv("CLOSET_THUMBNAIL_MAX_EDGE", "512")),
        closet_background_removal_provider=os.getenv(
            "CLOSET_BACKGROUND_REMOVAL_PROVIDER",
            "disabled",
        ).strip()
        or "disabled",
        photoroom_api_key=os.getenv("PHOTOROOM_API_KEY", "").strip(),
        photoroom_base_url=os.getenv("PHOTOROOM_BASE_URL", DEFAULT_PHOTOROOM_BASE_URL).strip()
        or DEFAULT_PHOTOROOM_BASE_URL,
        photoroom_timeout_seconds=float(os.getenv("PHOTOROOM_TIMEOUT_SECONDS", "30")),
        closet_metadata_extraction_provider=os.getenv(
            "CLOSET_METADATA_EXTRACTION_PROVIDER",
            "disabled",
        ).strip()
        or "disabled",
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_base_url=os.getenv("GEMINI_BASE_URL", DEFAULT_GEMINI_BASE_URL).strip()
        or DEFAULT_GEMINI_BASE_URL,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
        or "gemini-2.5-flash-lite",
        gemini_timeout_seconds=float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30")),
        closet_metadata_extraction_max_edge=int(
            os.getenv("CLOSET_METADATA_EXTRACTION_MAX_EDGE", "1600")
        ),
    )


settings = load_settings()
