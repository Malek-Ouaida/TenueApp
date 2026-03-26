from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)
app.include_router(api_router)
