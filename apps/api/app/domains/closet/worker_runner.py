from __future__ import annotations

import argparse
import time
from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient, S3StorageClient
from app.domains.closet.background_removal import (
    BackgroundRemovalProvider,
    build_background_removal_provider,
)
from app.domains.closet.image_processing_service import ClosetImageProcessingService
from app.domains.closet.models import ClosetJob, ProcessingRunType
from app.domains.closet.repository import ClosetJobRepository, ClosetRepository
from app.domains.closet.service import ClosetLifecycleService
from app.domains.closet.worker import JobHandler
from app.domains.closet.worker import run_once as run_worker_once


def build_storage_client() -> ObjectStorageClient:
    return S3StorageClient(
        endpoint_url=settings.minio_endpoint,
        region_name=settings.minio_region,
        access_key_id=settings.minio_access_key,
        secret_access_key=settings.minio_secret_key,
    )


def build_image_processing_handler(
    *,
    storage: ObjectStorageClient | None = None,
    background_removal_provider: BackgroundRemovalProvider | None = None,
) -> JobHandler:
    storage_client = storage or build_storage_client()
    provider = background_removal_provider or build_background_removal_provider()

    def handler(session: Session, job: ClosetJob) -> None:
        repository = ClosetRepository(session)
        lifecycle_service = ClosetLifecycleService(session=session, repository=repository)
        processing_service = ClosetImageProcessingService(
            session=session,
            repository=repository,
            job_repository=ClosetJobRepository(session),
            lifecycle_service=lifecycle_service,
            storage=storage_client,
            background_removal_provider=provider,
        )
        processing_service.handle_image_processing_job(job=job)

    return handler


def build_worker_handlers(
    *,
    storage: ObjectStorageClient | None = None,
    background_removal_provider: BackgroundRemovalProvider | None = None,
) -> Mapping[ProcessingRunType, JobHandler]:
    return {
        ProcessingRunType.IMAGE_PROCESSING: build_image_processing_handler(
            storage=storage,
            background_removal_provider=background_removal_provider,
        )
    }


def run_once(
    *,
    worker_name: str,
    storage: ObjectStorageClient | None = None,
    background_removal_provider: BackgroundRemovalProvider | None = None,
):
    return run_worker_once(
        worker_name,
        handlers=build_worker_handlers(
            storage=storage,
            background_removal_provider=background_removal_provider,
        ),
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
    parser = argparse.ArgumentParser(description="Run the closet image processing worker.")
    parser.add_argument("--once", action="store_true", help="Run at most one job and exit.")
    parser.add_argument(
        "--worker-name",
        default="closet-image-worker",
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
