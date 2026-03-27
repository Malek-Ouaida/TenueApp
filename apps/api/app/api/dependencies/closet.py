from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient, S3StorageClient
from app.db.session import get_db_session
from app.domains.closet.repository import ClosetRepository
from app.domains.closet.upload_service import ClosetDraftUploadService


@lru_cache(maxsize=1)
def get_storage_client() -> ObjectStorageClient:
    return S3StorageClient(
        endpoint_url=settings.minio_endpoint,
        region_name=settings.minio_region,
        access_key_id=settings.minio_access_key,
        secret_access_key=settings.minio_secret_key,
    )


def get_closet_upload_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> ClosetDraftUploadService:
    return ClosetDraftUploadService(
        session=db_session,
        repository=ClosetRepository(db_session),
        storage=storage_client,
    )
