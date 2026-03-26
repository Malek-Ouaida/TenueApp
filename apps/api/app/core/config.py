import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]
LOCAL_SUPABASE_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"

load_dotenv(REPO_ROOT / ".env")
load_dotenv(API_ROOT / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    database_url: str
    supabase_url: str
    supabase_anon_key: str
    supabase_auth_timeout_seconds: float


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Tenue API"),
        environment=os.getenv("APP_ENV", os.getenv("TENUE_ENV", "development")),
        database_url=os.getenv("DATABASE_URL", LOCAL_SUPABASE_DATABASE_URL),
        supabase_url=os.getenv("SUPABASE_URL", "http://127.0.0.1:54321"),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        supabase_auth_timeout_seconds=float(os.getenv("SUPABASE_AUTH_TIMEOUT_SECONDS", "10")),
    )


settings = load_settings()
