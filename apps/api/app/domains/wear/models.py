from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
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
    UniqueConstraint,
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
    PHOTO_DETECTED = "photo_detected"
    MIXED = "mixed"


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
        UniqueConstraint("outfit_id", "closet_item_id", name="uq_outfit_items_outfit_item"),
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
        Index("ix_wear_logs_user_wear_date", "user_id", "wear_date"),
        Index("ix_wear_logs_outfit_id", "outfit_id"),
        UniqueConstraint("user_id", "wear_date", name="uq_wear_logs_user_wear_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    wear_date: Mapped[date] = mapped_column(Date, nullable=False)
    outfit_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outfits.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[WearLogSource] = mapped_column(
        string_enum(WearLogSource),
        default=WearLogSource.MANUAL_ITEMS,
    )
    context: Mapped[WearContext | None] = mapped_column(
        string_enum(WearContext),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class WearLogItem(Base):
    __tablename__ = "wear_log_items"
    __table_args__ = (
        Index("ix_wear_log_items_log_sort", "wear_log_id", "sort_index"),
        Index("ix_wear_log_items_closet_item", "closet_item_id"),
        UniqueConstraint("wear_log_id", "closet_item_id", name="uq_wear_log_items_log_item"),
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

    wear_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wear_logs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    outfit_title_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    items_snapshot_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
