from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies.closet import get_storage_client
from app.api.schemas.health import HealthDependencySnapshot, HealthResponse, ReadinessResponse
from app.core.config import settings
from app.core.database_status import get_database_schema_status
from app.core.storage import ObjectStorageClient
from app.db.session import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    return HealthResponse(status="ok", service="api")


@router.get("/health/ready", response_model=ReadinessResponse)
def read_readiness(
    response: Response,
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> ReadinessResponse:
    dependencies: list[HealthDependencySnapshot] = []
    database_available = False

    try:
        db_session.execute(text("SELECT 1"))
        database_available = True
        dependencies.append(
            HealthDependencySnapshot(name="database", status="ok", critical=True, detail=None)
        )
    except Exception as exc:
        dependencies.append(
            HealthDependencySnapshot(
                name="database",
                status="error",
                critical=True,
                detail=str(exc),
            )
        )

    if database_available:
        schema_status = get_database_schema_status(db_session)
        dependencies.append(
            HealthDependencySnapshot(
                name="database_schema",
                status=schema_status.status,
                critical=schema_status.status != "skipped",
                detail=schema_status.detail,
            )
        )

    try:
        storage_client.generate_presigned_upload(
            bucket=settings.minio_bucket,
            key=f"health/ready/{uuid4()}",
            content_type="application/octet-stream",
            expires_in_seconds=60,
        )
        dependencies.append(
            HealthDependencySnapshot(name="object_storage", status="ok", critical=True, detail=None)
        )
    except Exception as exc:
        dependencies.append(
            HealthDependencySnapshot(
                name="object_storage",
                status="error",
                critical=True,
                detail=str(exc),
            )
        )

    background_provider_status = (
        "disabled"
        if settings.closet_background_removal_provider == "disabled"
        else "configured"
    )
    extraction_provider_status = (
        "disabled"
        if settings.closet_metadata_extraction_provider == "disabled"
        else "configured"
    )
    dependencies.append(
        HealthDependencySnapshot(
            name="background_removal_provider",
            status=background_provider_status,
            critical=False,
            detail=settings.closet_background_removal_provider,
        )
    )
    dependencies.append(
        HealthDependencySnapshot(
            name="metadata_extraction_provider",
            status=extraction_provider_status,
            critical=False,
            detail=settings.closet_metadata_extraction_provider,
        )
    )

    critical_failures = any(
        dependency.critical and dependency.status != "ok" for dependency in dependencies
    )
    if critical_failures:
        response.status_code = 503
        return ReadinessResponse(status="degraded", service="api", dependencies=dependencies)

    return ReadinessResponse(status="ok", service="api", dependencies=dependencies)
