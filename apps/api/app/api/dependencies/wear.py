from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies.closet import get_storage_client
from app.core.storage import ObjectStorageClient
from app.db.session import get_db_session
from app.domains.wear.detection import OutfitDetectionProvider, build_wear_detection_provider
from app.domains.wear.insight_service import InsightService
from app.domains.wear.matching_service import WearMatchingService
from app.domains.wear.outfit_service import OutfitService
from app.domains.wear.processing_service import WearProcessingService
from app.domains.wear.repository import WearJobRepository, WearRepository
from app.domains.wear.review_service import WearReviewService
from app.domains.wear.service import WearService
from app.domains.wear.upload_service import WearUploadService


@lru_cache(maxsize=1)
def get_wear_detection_provider() -> OutfitDetectionProvider:
    return build_wear_detection_provider()


def get_wear_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> WearService:
    return WearService(
        session=db_session,
        repository=WearRepository(db_session),
        storage=storage_client,
    )


def get_wear_matching_service(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> WearMatchingService:
    return WearMatchingService(
        session=db_session,
        repository=WearRepository(db_session),
    )


def get_wear_upload_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> WearUploadService:
    return WearUploadService(
        session=db_session,
        repository=WearRepository(db_session),
        job_repository=WearJobRepository(db_session),
        storage=storage_client,
    )


def get_wear_review_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> WearReviewService:
    return WearReviewService(
        session=db_session,
        repository=WearRepository(db_session),
        storage=storage_client,
    )


def get_wear_processing_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
    detection_provider: Annotated[OutfitDetectionProvider, Depends(get_wear_detection_provider)],
    matching_service: Annotated[WearMatchingService, Depends(get_wear_matching_service)],
) -> WearProcessingService:
    return WearProcessingService(
        session=db_session,
        repository=WearRepository(db_session),
        job_repository=WearJobRepository(db_session),
        storage=storage_client,
        detection_provider=detection_provider,
        matching_service=matching_service,
    )


def get_outfit_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> OutfitService:
    return OutfitService(
        session=db_session,
        repository=WearRepository(db_session),
        storage=storage_client,
    )


def get_insight_service(
    db_session: Annotated[Session, Depends(get_db_session)],
    storage_client: Annotated[ObjectStorageClient, Depends(get_storage_client)],
) -> InsightService:
    return InsightService(
        session=db_session,
        repository=WearRepository(db_session),
        storage=storage_client,
    )
