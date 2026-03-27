from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient, S3StorageClient
from app.db.session import get_db_session
from app.domains.closet.background_removal import (
    BackgroundRemovalProvider,
    build_background_removal_provider,
)
from app.domains.closet.image_processing_service import ClosetImageProcessingService
from app.domains.closet.repository import ClosetJobRepository, ClosetRepository
from app.domains.closet.service import ClosetLifecycleService
from app.domains.closet.upload_service import ClosetDraftUploadService


@lru_cache(maxsize=1)
def get_storage_client() -> ObjectStorageClient:
    return S3StorageClient(
        endpoint_url=settings.minio_endpoint,
        region_name=settings.minio_region,
        access_key_id=settings.minio_access_key,
        secret_access_key=settings.minio_secret_key,
    )


@lru_cache(maxsize=1)
def get_background_removal_provider() -> BackgroundRemovalProvider:
    return build_background_removal_provider()


def get_closet_image_processing_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
    background_removal_provider: Annotated[
        BackgroundRemovalProvider, Depends(get_background_removal_provider)
    ],
) -> ClosetImageProcessingService:
    repository = ClosetRepository(db_session)
    lifecycle_service = ClosetLifecycleService(session=db_session, repository=repository)
    return ClosetImageProcessingService(
        session=db_session,
        repository=repository,
        job_repository=ClosetJobRepository(db_session),
        lifecycle_service=lifecycle_service,
        storage=storage_client,
        background_removal_provider=background_removal_provider,
    )


def get_closet_upload_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
    image_processing_service: Annotated[
        ClosetImageProcessingService, Depends(get_closet_image_processing_service)
    ],
) -> ClosetDraftUploadService:
    return ClosetDraftUploadService(
        session=db_session,
        repository=ClosetRepository(db_session),
        storage=storage_client,
        image_processing_service=image_processing_service,
    )
