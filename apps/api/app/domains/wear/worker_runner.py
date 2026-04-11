from __future__ import annotations

import argparse
import time
from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient, S3StorageClient
from app.db.session import SessionLocal
from app.domains.wear.detection import OutfitDetectionProvider, build_wear_detection_provider
from app.domains.wear.matching_service import WearMatchingService
from app.domains.wear.models import WearEventJob, WearProcessingRunType
from app.domains.wear.processing_service import WearProcessingService
from app.domains.wear.repository import WearJobRepository, WearRepository
from app.domains.wear.worker import JobHandler
from app.domains.wear.worker import run_once as run_worker_once


def build_storage_client() -> ObjectStorageClient:
    return S3StorageClient(
        endpoint_url=settings.minio_endpoint,
        region_name=settings.minio_region,
        access_key_id=settings.minio_access_key,
        secret_access_key=settings.minio_secret_key,
    )


def build_photo_analysis_handler(
    *,
    storage: ObjectStorageClient | None = None,
    detection_provider: OutfitDetectionProvider | None = None,
) -> JobHandler:
    storage_client = storage or build_storage_client()
    provider = detection_provider or build_wear_detection_provider()

    def handler(session: Session, job: WearEventJob) -> None:
        repository = WearRepository(session)
        processing_service = WearProcessingService(
            session=session,
            repository=repository,
            job_repository=WearJobRepository(session),
            storage=storage_client,
            detection_provider=provider,
            matching_service=WearMatchingService(
                session=session,
                repository=repository,
            ),
        )
        processing_service.handle_photo_analysis_job(wear_log_id=job.wear_log_id)

    return handler


def build_worker_handlers(
    *,
    storage: ObjectStorageClient | None = None,
    detection_provider: OutfitDetectionProvider | None = None,
) -> Mapping[WearProcessingRunType, JobHandler]:
    return {
        WearProcessingRunType.PHOTO_ANALYSIS: build_photo_analysis_handler(
            storage=storage,
            detection_provider=detection_provider,
        ),
    }


def run_once(
    *,
    worker_name: str,
    storage: ObjectStorageClient | None = None,
    detection_provider: OutfitDetectionProvider | None = None,
):
    return run_worker_once(
        worker_name,
        handlers=build_worker_handlers(storage=storage, detection_provider=detection_provider),
    )


def run_forever(
    *,
    worker_name: str,
    poll_interval_seconds: float,
) -> None:
    while True:
        job_id = run_once(worker_name=worker_name)
        if job_id is None:
            time.sleep(poll_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the wear-event worker.")
    parser.add_argument("--once", action="store_true", help="Run at most one job and exit.")
    parser.add_argument(
        "--worker-name",
        default="wear-worker",
        help="Worker lock name for claimed jobs.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=2.0,
        help="Sleep interval between polling attempts when no jobs are available.",
    )
    args = parser.parse_args()

    if args.once:
        run_once(worker_name=args.worker_name)
        return

    run_forever(
        worker_name=args.worker_name,
        poll_interval_seconds=args.poll_interval_seconds,
    )


if __name__ == "__main__":
    main()
