from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def string_enum(enum_cls: type[Enum]) -> SqlEnum:
    return SqlEnum(
        enum_cls,
        native_enum=False,
        values_callable=enum_values,
        validate_strings=True,
    )


class LifecycleStatus(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    REVIEW = "review"
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ISSUES = "completed_with_issues"
    FAILED = "failed"


class ReviewStatus(str, Enum):
    NEEDS_REVIEW = "needs_review"
    READY_TO_CONFIRM = "ready_to_confirm"
    CONFIRMED = "confirmed"


class MediaAssetSourceKind(str, Enum):
    UPLOAD = "upload"
    PROCESSED = "processed"
    DERIVED = "derived"
    REFERENCE = "reference"


class ClosetItemImageRole(str, Enum):
    ORIGINAL = "original"
    PROCESSED = "processed"
    THUMBNAIL = "thumbnail"
    MASK = "mask"
    REFERENCE = "reference"


class ProcessingRunType(str, Enum):
    UPLOAD_VALIDATION = "upload_validation"
    ASSET_PROMOTION = "asset_promotion"
    IMAGE_PROCESSING = "image_processing"
    METADATA_EXTRACTION = "metadata_extraction"
    NORMALIZATION_PROJECTION = "normalization_projection"
    SIMILARITY_RECOMPUTE = "similarity_recompute"


class ProviderResultStatus(str, Enum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class ApplicabilityState(str, Enum):
    VALUE = "value"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class FieldSource(str, Enum):
    PROVIDER = "provider"
    USER = "user"
    SYSTEM = "system"


class FieldReviewState(str, Enum):
    PENDING_USER = "pending_user"
    USER_CONFIRMED = "user_confirmed"
    USER_EDITED = "user_edited"
    SYSTEM_UNSET = "system_unset"


class AuditActorType(str, Enum):
    USER = "user"
    SYSTEM = "system"
    WORKER = "worker"


class SimilarityType(str, Enum):
    SIMILAR = "similar"
    DUPLICATE_CANDIDATE = "duplicate_candidate"
    DUPLICATE = "duplicate"


class SimilarityDecisionStatus(str, Enum):
    PENDING = "pending"
    DISMISSED = "dismissed"
    MARKED_DUPLICATE = "marked_duplicate"


class ClosetJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadIntentStatus(str, Enum):
    PENDING = "pending"
    FINALIZED = "finalized"
    EXPIRED = "expired"
    FAILED = "failed"


class ClosetItem(Base):
    __tablename__ = "closet_items"
    __table_args__ = (
        Index(
            "ix_closet_items_user_lifecycle_review",
            "user_id",
            "lifecycle_status",
            "review_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        string_enum(LifecycleStatus),
        default=LifecycleStatus.DRAFT,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        string_enum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        string_enum(ReviewStatus),
        default=ReviewStatus.NEEDS_REVIEW,
    )
    primary_image_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (Index("ix_media_assets_checksum", "checksum"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    bucket: Mapped[str] = mapped_column(String(128))
    key: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(128))
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_kind: Mapped[MediaAssetSourceKind] = mapped_column(
        string_enum(MediaAssetSourceKind),
        default=MediaAssetSourceKind.UPLOAD,
    )
    is_private: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ClosetItemImage(Base):
    __tablename__ = "closet_item_images"
    __table_args__ = (Index("ix_closet_item_images_item_role", "closet_item_id", "role"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
    )
    role: Mapped[ClosetItemImageRole] = mapped_column(
        string_enum(ClosetItemImageRole),
        default=ClosetItemImageRole.ORIGINAL,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    run_type: Mapped[ProcessingRunType] = mapped_column(string_enum(ProcessingRunType))
    status: Mapped[ProcessingStatus] = mapped_column(string_enum(ProcessingStatus))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_payload: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ProviderResult(Base):
    __tablename__ = "provider_results"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    processing_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("processing_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_name: Mapped[str] = mapped_column(String(64))
    provider_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[ProviderResultStatus] = mapped_column(string_enum(ProviderResultStatus))
    raw_payload: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClosetItemFieldCandidate(Base):
    __tablename__ = "closet_item_field_candidates"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    field_name: Mapped[str] = mapped_column(String(64))
    raw_value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    normalized_candidate: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider_result_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("provider_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    applicability_state: Mapped[ApplicabilityState] = mapped_column(string_enum(ApplicabilityState))
    conflict_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClosetItemFieldState(Base):
    __tablename__ = "closet_item_field_states"
    __table_args__ = (
        Index(
            "ux_closet_item_field_states_item_field",
            "closet_item_id",
            "field_name",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    field_name: Mapped[str] = mapped_column(String(64))
    canonical_value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    source: Mapped[FieldSource] = mapped_column(string_enum(FieldSource))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_state: Mapped[FieldReviewState] = mapped_column(string_enum(FieldReviewState))
    applicability_state: Mapped[ApplicabilityState] = mapped_column(string_enum(ApplicabilityState))
    taxonomy_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ClosetItemMetadataProjection(Base):
    __tablename__ = "closet_item_metadata_projection"
    __table_args__ = (
        Index("ux_closet_item_metadata_projection_item", "closet_item_id", unique=True),
        Index(
            "ix_closet_meta_proj_user_cat_subcat_color",
            "user_id",
            "category",
            "subcategory",
            "primary_color",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    taxonomy_version: Mapped[str] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    secondary_colors: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    material: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pattern: Mapped[str | None] = mapped_column(String(64), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    style_tags: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    occasion_tags: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    season_tags: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ClosetItemAuditEvent(Base):
    __tablename__ = "closet_item_audit_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_type: Mapped[AuditActorType] = mapped_column(string_enum(AuditActorType))
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClosetItemSimilarityEdge(Base):
    __tablename__ = "closet_item_similarity_edges"
    __table_args__ = (
        CheckConstraint("item_a_id <> item_b_id", name="ck_similarity_edge_distinct_items"),
        Index(
            "ux_closet_item_similarity_edges_canonical_pair",
            "item_a_id",
            "item_b_id",
            "similarity_type",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    item_a_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    item_b_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    similarity_type: Mapped[SimilarityType] = mapped_column(string_enum(SimilarityType))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    signals_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    decision_status: Mapped[SimilarityDecisionStatus] = mapped_column(
        string_enum(SimilarityDecisionStatus),
        default=SimilarityDecisionStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ClosetJob(Base):
    __tablename__ = "closet_jobs"
    __table_args__ = (Index("ix_closet_jobs_status_available_at", "status", "available_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    job_kind: Mapped[ProcessingRunType] = mapped_column(string_enum(ProcessingRunType))
    status: Mapped[ClosetJobStatus] = mapped_column(
        string_enum(ClosetJobStatus),
        default=ClosetJobStatus.PENDING,
    )
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    payload: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ClosetUploadIntent(Base):
    __tablename__ = "closet_upload_intents"
    __table_args__ = (
        Index("ix_closet_upload_intents_user_status_created", "user_id", "status", "created_at"),
        Index(
            "ix_closet_upload_intents_item_status_expires",
            "closet_item_id",
            "status",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    staging_bucket: Mapped[str] = mapped_column(String(128))
    staging_key: Mapped[str] = mapped_column(String(512))
    status: Mapped[UploadIntentStatus] = mapped_column(
        string_enum(UploadIntentStatus),
        default=UploadIntentStatus.PENDING,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ClosetIdempotencyKey(Base):
    __tablename__ = "closet_idempotency_keys"
    __table_args__ = (
        Index(
            "ux_closet_idempotency_keys_user_operation_key",
            "user_id",
            "operation",
            "idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    operation: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True))
    response_status_code: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )
