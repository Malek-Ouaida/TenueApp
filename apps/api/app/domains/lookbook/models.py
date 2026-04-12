from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
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


class LookbookEntryType(str, Enum):
    OUTFIT = "outfit"
    IMAGE = "image"
    NOTE = "note"


class LookbookEntrySourceKind(str, Enum):
    GALLERY_PHOTO = "gallery_photo"
    WEAR_LOG = "wear_log"


class LookbookEntryIntent(str, Enum):
    INSPIRATION = "inspiration"
    RECREATE = "recreate"
    LOGGED = "logged"


class LookbookEntryStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class LookbookUploadIntentStatus(str, Enum):
    PENDING = "pending"
    FINALIZED = "finalized"
    EXPIRED = "expired"
    FAILED = "failed"


class Lookbook(Base):
    __tablename__ = "lookbooks"
    __table_args__ = (
        Index("ix_lookbooks_user_updated_id", "user_id", "updated_at", "id"),
        Index("ix_lookbooks_user_default", "user_id", "is_default", "updated_at", "id"),
        Index(
            "uq_lookbooks_user_single_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default = 1"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class LookbookEntry(Base):
    __tablename__ = "lookbook_entries"
    __table_args__ = (
        Index("ix_lookbook_entries_lookbook_sort", "lookbook_id", "sort_index"),
        Index("ix_lookbook_entries_feed_updated", "lookbook_id", "archived_at", "updated_at", "id"),
        Index("ix_lookbook_entries_status_updated", "lookbook_id", "status", "updated_at", "id"),
        Index("ix_lookbook_entries_source_wear_log", "source_wear_log_id"),
        Index("ix_lookbook_entries_owned_outfit", "owned_outfit_id"),
        Index(
            "uq_lookbook_entries_active_source_wear_log",
            "source_wear_log_id",
            unique=True,
            postgresql_where=text("source_wear_log_id IS NOT NULL AND archived_at IS NULL"),
            sqlite_where=text("source_wear_log_id IS NOT NULL AND archived_at IS NULL"),
        ),
        CheckConstraint(
            "("
            "entry_type = 'outfit' AND outfit_id IS NOT NULL AND image_asset_id IS NULL "
            "AND note_text IS NULL"
            ") OR ("
            "entry_type = 'image' AND outfit_id IS NULL AND image_asset_id IS NOT NULL "
            "AND note_text IS NULL"
            ") OR ("
            "entry_type = 'note' AND outfit_id IS NULL AND image_asset_id IS NULL "
            "AND note_text IS NOT NULL AND caption IS NULL"
            ")",
            name="ck_lookbook_entries_entry_payload",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lookbook_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lookbooks.id", ondelete="CASCADE"),
    )
    # Legacy columns kept to remain compatible with the existing migration history.
    entry_type: Mapped[LookbookEntryType] = mapped_column(
        string_enum(LookbookEntryType),
        default=LookbookEntryType.IMAGE,
    )
    outfit_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outfits.id"),
        nullable=True,
    )
    image_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id"),
        nullable=True,
    )
    caption: Mapped[str | None] = mapped_column(String(280), nullable=True)
    note_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    source_kind: Mapped[LookbookEntrySourceKind] = mapped_column(
        string_enum(LookbookEntrySourceKind),
        default=LookbookEntrySourceKind.GALLERY_PHOTO,
    )
    intent: Mapped[LookbookEntryIntent] = mapped_column(
        string_enum(LookbookEntryIntent),
        default=LookbookEntryIntent.INSPIRATION,
    )
    status: Mapped[LookbookEntryStatus] = mapped_column(
        string_enum(LookbookEntryStatus),
        default=LookbookEntryStatus.DRAFT,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    occasion_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    season_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    style_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_wear_log_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="SET NULL"),
        nullable=True,
    )
    owned_outfit_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outfits.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_snapshot_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class LookbookUploadIntent(Base):
    __tablename__ = "lookbook_upload_intents"
    __table_args__ = (
        Index(
            "ix_lookbook_upload_intents_user_status_created",
            "user_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_lookbook_upload_intents_lookbook_status_expires",
            "lookbook_id",
            "status",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lookbook_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lookbooks.id", ondelete="CASCADE"),
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
    status: Mapped[LookbookUploadIntentStatus] = mapped_column(
        string_enum(LookbookUploadIntentStatus),
        default=LookbookUploadIntentStatus.PENDING,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
