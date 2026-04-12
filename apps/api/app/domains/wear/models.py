from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy import Enum as SqlEnum
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


class WearLogSource(str, Enum):
    MANUAL_ITEMS = "manual_items"
    SAVED_OUTFIT = "saved_outfit"
    PHOTO_UPLOAD = "photo_upload"
    PHOTO_DETECTED = "photo_detected"
    MIXED = "mixed"


class WearLogStatus(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class WearTimePrecision(str, Enum):
    DATE_ONLY = "date_only"
    APPROXIMATE = "approximate"
    EXACT = "exact"


class WearContext(str, Enum):
    CASUAL = "casual"
    WORK = "work"
    EVENT = "event"
    TRAVEL = "travel"
    GYM = "gym"
    LOUNGE = "lounge"


class WearItemSource(str, Enum):
    MANUAL = "manual"
    FROM_OUTFIT = "from_outfit"
    AI_MATCHED = "ai_matched"
    MANUAL_OVERRIDE = "manual_override"


class WearItemRole(str, Enum):
    TOP = "top"
    BOTTOM = "bottom"
    DRESS = "dress"
    OUTERWEAR = "outerwear"
    SHOES = "shoes"
    BAG = "bag"
    ACCESSORY = "accessory"
    OTHER = "other"


class WearUploadIntentStatus(str, Enum):
    PENDING = "pending"
    FINALIZED = "finalized"
    EXPIRED = "expired"
    FAILED = "failed"


class WearDetectedItemStatus(str, Enum):
    DETECTED = "detected"
    EXCLUDED = "excluded"
    CONFIRMED = "confirmed"


class WearProcessingRunType(str, Enum):
    PHOTO_ANALYSIS = "photo_analysis"


class WearProcessingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WearProviderResultStatus(str, Enum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class WearJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OutfitSource(str, Enum):
    MANUAL = "manual"
    DERIVED_FROM_WEAR_LOG = "derived_from_wear_log"
    AI_SUGGESTED = "ai_suggested"


class OutfitSeason(str, Enum):
    SUMMER = "summer"
    WINTER = "winter"


class Outfit(Base):
    __tablename__ = "outfits"
    __table_args__ = (
        Index("ix_outfits_user_archived_updated", "user_id", "archived_at", "updated_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    occasion: Mapped[WearContext | None] = mapped_column(
        string_enum(WearContext),
        nullable=True,
    )
    season: Mapped[OutfitSeason | None] = mapped_column(
        string_enum(OutfitSeason),
        nullable=True,
    )
    source: Mapped[OutfitSource] = mapped_column(
        string_enum(OutfitSource),
        default=OutfitSource.MANUAL,
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class OutfitItem(Base):
    __tablename__ = "outfit_items"
    __table_args__ = (
        Index("ix_outfit_items_outfit_sort", "outfit_id", "sort_index"),
        Index("ux_outfit_items_outfit_item", "outfit_id", "closet_item_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    outfit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outfits.id", ondelete="CASCADE"),
    )
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    role: Mapped[WearItemRole | None] = mapped_column(
        string_enum(WearItemRole),
        nullable=True,
    )
    layer_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WearLog(Base):
    __tablename__ = "wear_logs"
    __table_args__ = (
        Index("ix_wear_logs_user_calendar", "user_id", "wear_date", "worn_at", "id"),
        Index("ix_wear_logs_user_status_worn_at", "user_id", "status", "archived_at", "worn_at"),
        Index("ix_wear_logs_outfit_id", "outfit_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    wear_date: Mapped[date] = mapped_column(Date, nullable=False)
    worn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    worn_time_precision: Mapped[WearTimePrecision] = mapped_column(
        string_enum(WearTimePrecision),
        default=WearTimePrecision.DATE_ONLY,
    )
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outfit_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outfits.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[WearLogSource] = mapped_column(
        string_enum(WearLogSource),
        default=WearLogSource.MANUAL_ITEMS,
    )
    status: Mapped[WearLogStatus] = mapped_column(
        string_enum(WearLogStatus),
        default=WearLogStatus.CONFIRMED,
    )
    context: Mapped[WearContext | None] = mapped_column(
        string_enum(WearContext),
        nullable=True,
    )
    vibe: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    primary_photo_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    confirmed_item_count: Mapped[int] = mapped_column(Integer, default=0)
    combination_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class WearEventPhoto(Base):
    __tablename__ = "wear_event_photos"
    __table_args__ = (
        Index("ix_wear_event_photos_log_position", "wear_log_id", "position"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    wear_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="CASCADE"),
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
    )
    thumbnail_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class WearEventUploadIntent(Base):
    __tablename__ = "wear_event_upload_intents"
    __table_args__ = (
        Index("ix_wear_event_upload_intents_user_status_created", "user_id", "status", "created_at"),
        Index(
            "ix_wear_event_upload_intents_log_status_expires",
            "wear_log_id",
            "status",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    wear_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="CASCADE"),
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
    status: Mapped[WearUploadIntentStatus] = mapped_column(
        string_enum(WearUploadIntentStatus),
        default=WearUploadIntentStatus.PENDING,
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


class WearEventProcessingRun(Base):
    __tablename__ = "wear_event_processing_runs"
    __table_args__ = (
        Index(
            "ix_wear_event_processing_runs_log_run_type_created",
            "wear_log_id",
            "run_type",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    wear_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="CASCADE"),
    )
    run_type: Mapped[WearProcessingRunType] = mapped_column(string_enum(WearProcessingRunType))
    status: Mapped[WearProcessingStatus] = mapped_column(string_enum(WearProcessingStatus))
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


class WearEventProviderResult(Base):
    __tablename__ = "wear_event_provider_results"
    __table_args__ = (
        Index("ix_wear_event_provider_results_run_created", "processing_run_id", "created_at"),
        Index(
            "ix_wear_event_provider_results_log_task_created",
            "wear_log_id",
            "task_type",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    wear_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="CASCADE"),
    )
    processing_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_event_processing_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_name: Mapped[str] = mapped_column(String(64))
    provider_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[WearProviderResultStatus] = mapped_column(
        string_enum(WearProviderResultStatus)
    )
    raw_payload: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WearEventDetectedItem(Base):
    __tablename__ = "wear_event_detected_items"
    __table_args__ = (
        Index("ix_wear_event_detected_items_log_sort", "wear_log_id", "sort_index"),
        Index(
            "ix_wear_event_detected_items_run_created",
            "processing_run_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    wear_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="CASCADE"),
    )
    processing_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_event_processing_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    predicted_role: Mapped[WearItemRole | None] = mapped_column(
        string_enum(WearItemRole),
        nullable=True,
    )
    predicted_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    predicted_subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)
    predicted_colors_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Metadata-first matching fields
    predicted_material: Mapped[str | None] = mapped_column(String(64), nullable=True)
    predicted_pattern: Mapped[str | None] = mapped_column(String(64), nullable=True)
    predicted_fit_tags_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    predicted_silhouette: Mapped[str | None] = mapped_column(String(64), nullable=True)
    predicted_attributes_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    normalized_metadata_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    field_confidences_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    matching_explanation_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_json: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    crop_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[WearDetectedItemStatus] = mapped_column(
        string_enum(WearDetectedItemStatus),
        default=WearDetectedItemStatus.DETECTED,
    )
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class WearEventMatchCandidate(Base):
    __tablename__ = "wear_event_match_candidates"
    __table_args__ = (
        Index("ix_wear_event_match_candidates_detected_rank", "detected_item_id", "rank"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    detected_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_event_detected_items.id", ondelete="CASCADE"),
    )
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    signals_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WearLogItem(Base):
    __tablename__ = "wear_log_items"
    __table_args__ = (
        Index("ix_wear_log_items_log_sort", "wear_log_id", "sort_index"),
        Index("ix_wear_log_items_closet_item", "closet_item_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    wear_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="CASCADE"),
    )
    closet_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("closet_items.id", ondelete="CASCADE"),
    )
    detected_item_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_event_detected_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[WearItemSource] = mapped_column(
        string_enum(WearItemSource),
        default=WearItemSource.MANUAL,
    )
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    role: Mapped[WearItemRole | None] = mapped_column(
        string_enum(WearItemRole),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WearLogSnapshot(Base):
    __tablename__ = "wear_log_snapshots"
    __table_args__ = (
        Index("ux_wear_log_snapshots_wear_log", "wear_log_id", unique=True),
    )

    wear_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    outfit_title_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    items_snapshot_json: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class WearEventJob(Base):
    __tablename__ = "wear_event_jobs"
    __table_args__ = (
        Index("ix_wear_event_jobs_status_available_at", "status", "available_at"),
        Index("ix_wear_event_jobs_log_kind_status", "wear_log_id", "job_kind", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    wear_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="CASCADE"),
    )
    job_kind: Mapped[WearProcessingRunType] = mapped_column(string_enum(WearProcessingRunType))
    status: Mapped[WearJobStatus] = mapped_column(
        string_enum(WearJobStatus),
        default=WearJobStatus.PENDING,
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
