from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.auth.models import User
from app.domains.closet.errors import (
    INVALID_LIFECYCLE_TRANSITION,
    MISSING_REQUIRED_CONFIRMATION_FIELDS,
    ClosetDomainError,
)
from app.domains.closet.models import (
    ApplicabilityState,
    AuditActorType,
    ClosetItemFieldState,
    ClosetJobStatus,
    FieldReviewState,
    FieldSource,
    LifecycleStatus,
    MediaAssetSourceKind,
    ProcessingRunType,
    ProcessingStatus,
    ReviewStatus,
)
from app.domains.closet.repository import ClosetJobRepository, ClosetRepository
from app.domains.closet.service import ClosetLifecycleService
from app.domains.closet.taxonomy import TAXONOMY_VERSION
from app.domains.closet.worker import ClosetWorker


def create_user(session: Session, *, email: str = "closet-owner@example.com") -> User:
    user = User(
        email=email,
        auth_provider="supabase",
        auth_subject=str(uuid4()),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_service(session: Session) -> ClosetLifecycleService:
    return ClosetLifecycleService(session=session, repository=ClosetRepository(session))


def normalize_test_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is None else value.astimezone(UTC).replace(tzinfo=None)


def create_ready_for_review_item(
    session: Session,
    user: User,
) -> tuple[ClosetLifecycleService, UUID]:
    service = create_service(session)
    item = service.create_item(user_id=user.id)
    asset = service.create_media_asset(
        user_id=user.id,
        bucket="closet",
        key="items/item-1.jpg",
        mime_type="image/jpeg",
        file_size=1024,
        checksum="checksum-1",
        width=640,
        height=960,
        source_kind=MediaAssetSourceKind.UPLOAD,
    )
    item = service.attach_primary_asset(item_id=item.id, user_id=user.id, asset_id=asset.id)
    item = service.update_processing_state(
        item_id=item.id,
        user_id=user.id,
        processing_status=ProcessingStatus.RUNNING,
    )
    assert item.lifecycle_status == LifecycleStatus.PROCESSING
    item = service.update_processing_state(
        item_id=item.id,
        user_id=user.id,
        processing_status=ProcessingStatus.COMPLETED,
    )
    assert item.lifecycle_status == LifecycleStatus.REVIEW
    return service, item.id


def confirm_required_fields(
    service: ClosetLifecycleService,
    *,
    item_id: UUID,
    user: User,
) -> None:
    service.upsert_field_state(
        item_id=item_id,
        user_id=user.id,
        field_name="category",
        canonical_value="tops",
        source=FieldSource.USER,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
        taxonomy_version=TAXONOMY_VERSION,
    )
    service.upsert_field_state(
        item_id=item_id,
        user_id=user.id,
        field_name="subcategory",
        canonical_value="t-shirt",
        source=FieldSource.USER,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
        taxonomy_version=TAXONOMY_VERSION,
    )


def test_lifecycle_service_allows_draft_to_processing_to_review_to_confirmed(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    service, item_id = create_ready_for_review_item(db_session, user)

    confirm_required_fields(service, item_id=item_id, user=user)
    item = service.confirm_item(item_id=item_id, user_id=user.id)

    assert item.lifecycle_status == LifecycleStatus.CONFIRMED
    assert item.review_status == ReviewStatus.CONFIRMED
    assert item.confirmed_at is not None


def test_lifecycle_service_rejects_draft_to_confirmed(db_session: Session) -> None:
    user = create_user(db_session)
    service = create_service(db_session)
    item = service.create_item(user_id=user.id)

    with pytest.raises(ClosetDomainError) as exc_info:
        service.confirm_item(item_id=item.id, user_id=user.id)

    error = exc_info.value
    assert error.code == INVALID_LIFECYCLE_TRANSITION


def test_confirm_rejects_missing_required_fields(db_session: Session) -> None:
    user = create_user(db_session)
    service, item_id = create_ready_for_review_item(db_session, user)
    service.upsert_field_state(
        item_id=item_id,
        user_id=user.id,
        field_name="category",
        canonical_value="tops",
        source=FieldSource.USER,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
        taxonomy_version=TAXONOMY_VERSION,
    )

    with pytest.raises(ClosetDomainError) as exc_info:
        service.confirm_item(item_id=item_id, user_id=user.id)

    error = exc_info.value
    assert error.code == MISSING_REQUIRED_CONFIRMATION_FIELDS


def test_review_status_only_becomes_ready_when_minimum_fields_exist(db_session: Session) -> None:
    user = create_user(db_session)
    service, item_id = create_ready_for_review_item(db_session, user)

    item = service.recompute_review_readiness(item_id=item_id, user_id=user.id)
    assert item.review_status == ReviewStatus.NEEDS_REVIEW

    service.upsert_field_state(
        item_id=item_id,
        user_id=user.id,
        field_name="category",
        canonical_value="tops",
        source=FieldSource.USER,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
        taxonomy_version=TAXONOMY_VERSION,
    )
    item = service.recompute_review_readiness(item_id=item_id, user_id=user.id)
    assert item.review_status == ReviewStatus.NEEDS_REVIEW

    service.upsert_field_state(
        item_id=item_id,
        user_id=user.id,
        field_name="subcategory",
        canonical_value="t-shirt",
        source=FieldSource.USER,
        review_state=FieldReviewState.USER_EDITED,
        applicability_state=ApplicabilityState.VALUE,
        taxonomy_version=TAXONOMY_VERSION,
    )
    item = service.recompute_review_readiness(item_id=item_id, user_id=user.id)
    assert item.review_status == ReviewStatus.READY_TO_CONFIRM


def test_archived_items_cannot_transition_again(db_session: Session) -> None:
    user = create_user(db_session)
    service, item_id = create_ready_for_review_item(db_session, user)
    confirm_required_fields(service, item_id=item_id, user=user)
    service.confirm_item(item_id=item_id, user_id=user.id)
    item = service.archive_item(item_id=item_id, user_id=user.id)

    assert item.lifecycle_status == LifecycleStatus.ARCHIVED

    with pytest.raises(ClosetDomainError) as exc_info:
        service.update_processing_state(
            item_id=item_id,
            user_id=user.id,
            processing_status=ProcessingStatus.RUNNING,
        )

    error = exc_info.value
    assert error.code == INVALID_LIFECYCLE_TRANSITION


def test_unique_field_state_constraint_prevents_duplicate_current_field_states(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    service = create_service(db_session)
    item = service.create_item(user_id=user.id)

    first_state = ClosetItemFieldState(
        closet_item_id=item.id,
        field_name="category",
        canonical_value="tops",
        source=FieldSource.USER,
        confidence=1.0,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
        taxonomy_version=TAXONOMY_VERSION,
    )
    duplicate_state = ClosetItemFieldState(
        closet_item_id=item.id,
        field_name="category",
        canonical_value="bottoms",
        source=FieldSource.USER,
        confidence=1.0,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
        taxonomy_version=TAXONOMY_VERSION,
    )

    db_session.add(first_state)
    db_session.commit()
    db_session.add(duplicate_state)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_job_queue_claim_only_returns_claimable_jobs(db_session: Session) -> None:
    user = create_user(db_session)
    service = create_service(db_session)
    item = service.create_item(user_id=user.id)
    repository = ClosetJobRepository(db_session)
    now = datetime.now(UTC)

    claimable_job = repository.enqueue_job(
        closet_item_id=item.id,
        job_kind=ProcessingRunType.IMAGE_PROCESSING,
        available_at=now - timedelta(minutes=1),
    )
    future_job = repository.enqueue_job(
        closet_item_id=item.id,
        job_kind=ProcessingRunType.METADATA_EXTRACTION,
        available_at=now + timedelta(minutes=5),
    )
    running_job = repository.enqueue_job(
        closet_item_id=item.id,
        job_kind=ProcessingRunType.SIMILARITY_RECOMPUTE,
        available_at=now - timedelta(minutes=1),
    )
    repository.mark_job_running(job=running_job, worker_name="seed-worker", now=now)
    db_session.commit()

    claimed = repository.claim_next_job(worker_name="worker-1", now=now)

    assert claimed is not None
    assert claimed.id == claimable_job.id
    assert claimed.status == ClosetJobStatus.RUNNING
    assert claimed.locked_by == "worker-1"

    claimed_again = repository.claim_next_job(worker_name="worker-2", now=now)
    assert claimed_again is None
    assert future_job.status == ClosetJobStatus.PENDING


def test_confirm_and_archive_record_audit_events(db_session: Session) -> None:
    user = create_user(db_session)
    service, item_id = create_ready_for_review_item(db_session, user)
    confirm_required_fields(service, item_id=item_id, user=user)
    confirmed_item = service.confirm_item(item_id=item_id, user_id=user.id)
    assert confirmed_item.lifecycle_status == LifecycleStatus.CONFIRMED
    archived_item = service.archive_item(item_id=item_id, user_id=user.id)

    events = ClosetRepository(db_session).list_audit_events(closet_item_id=archived_item.id)
    event_types = [event.event_type for event in events]

    assert archived_item.lifecycle_status == LifecycleStatus.ARCHIVED
    assert "item_confirmed" in event_types
    assert "item_archived" in event_types

    confirm_event = next(event for event in events if event.event_type == "item_confirmed")
    archive_event = next(event for event in events if event.event_type == "item_archived")
    assert confirm_event.actor_type == AuditActorType.USER
    assert archive_event.actor_type == AuditActorType.USER


def test_release_job_for_retry_applies_exponential_backoff(db_session: Session) -> None:
    user = create_user(db_session, email="job-retry-backoff@example.com")
    service = create_service(db_session)
    item = service.create_item(user_id=user.id)
    repository = ClosetJobRepository(db_session)
    now = datetime.now(UTC)
    job = repository.enqueue_job(
        closet_item_id=item.id,
        job_kind=ProcessingRunType.IMAGE_PROCESSING,
        available_at=now - timedelta(minutes=1),
        max_attempts=4,
    )
    repository.mark_job_running(job=job, worker_name="worker-1", now=now)

    retried_job = repository.release_job_for_retry(
        job=job,
        error_code="job_handler_failed",
        error_detail="boom",
        now=now,
    )

    assert retried_job.status == ClosetJobStatus.PENDING
    assert retried_job.locked_at is None
    assert retried_job.locked_by is None
    assert retried_job.last_error_code == "job_handler_failed"
    assert retried_job.last_error_detail == "boom"
    assert (
        normalize_test_datetime(retried_job.available_at) - normalize_test_datetime(now)
    ).total_seconds() == settings.closet_job_retry_base_delay_seconds


def test_claim_next_job_reclaims_stale_running_jobs(db_session: Session) -> None:
    user = create_user(db_session, email="job-retry-stale@example.com")
    service = create_service(db_session)
    item = service.create_item(user_id=user.id)
    repository = ClosetJobRepository(db_session)
    now = datetime.now(UTC)
    stale_lock_time = now - timedelta(seconds=settings.closet_job_lock_timeout_seconds + 1)
    job = repository.enqueue_job(
        closet_item_id=item.id,
        job_kind=ProcessingRunType.IMAGE_PROCESSING,
        available_at=stale_lock_time,
        max_attempts=3,
    )
    repository.mark_job_running(job=job, worker_name="stale-worker", now=stale_lock_time)
    db_session.commit()

    claimed = repository.claim_next_job(worker_name="worker-2", now=now)

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == ClosetJobStatus.RUNNING
    assert claimed.locked_by == "worker-2"
    assert claimed.attempt_count == 2
    assert claimed.last_error_code == "job_lock_expired"


def test_worker_retries_unhandled_failures_until_max_attempts(db_session: Session) -> None:
    user = create_user(db_session, email="job-worker-retry@example.com")
    service = create_service(db_session)
    item = service.create_item(user_id=user.id)
    repository = ClosetJobRepository(db_session)
    job = repository.enqueue_job(
        closet_item_id=item.id,
        job_kind=ProcessingRunType.IMAGE_PROCESSING,
        max_attempts=2,
    )
    db_session.commit()

    def failing_handler(session: Session, claimed_job: object) -> None:
        del session, claimed_job
        raise RuntimeError("boom")

    worker = ClosetWorker(
        session=db_session,
        handlers={ProcessingRunType.IMAGE_PROCESSING: failing_handler},
    )

    first_job = worker.run_once(worker_name="worker-1")
    db_session.refresh(job)

    assert first_job is not None
    assert job.status == ClosetJobStatus.PENDING
    assert job.attempt_count == 1
    assert job.last_error_code == "job_handler_failed"

    job.available_at = normalize_test_datetime(datetime.now(UTC) - timedelta(seconds=1))
    db_session.commit()

    second_job = worker.run_once(worker_name="worker-1")
    db_session.refresh(job)

    assert second_job is not None
    assert job.status == ClosetJobStatus.FAILED
    assert job.attempt_count == 2
    assert job.last_error_code == "job_handler_failed"
