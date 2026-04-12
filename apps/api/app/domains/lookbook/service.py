from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient
from app.domains.closet.image_processing_service import ProcessingSnapshotImage
from app.domains.closet.models import MediaAsset, utcnow
from app.domains.closet.taxonomy import OCCASION_TAGS, SEASON_TAGS, STYLE_TAGS
from app.domains.lookbook.errors import LookbookError
from app.domains.lookbook.models import (
    Lookbook,
    LookbookEntry,
    LookbookEntryIntent,
    LookbookEntrySourceKind,
    LookbookEntryStatus,
)
from app.domains.lookbook.repository import LookbookRepository
from app.domains.wear.models import OutfitSource
from app.domains.wear.outfit_service import (
    OutfitDetailSnapshot as OutfitDetailView,
)
from app.domains.wear.outfit_service import OutfitService
from app.domains.wear.service import WearLogDetailSnapshot as WearLogDetailView
from app.domains.wear.service import WearService
from app.domains.wear.repository import WearRepository

logger = logging.getLogger(__name__)

_LOOKBOOK_DEFAULT_TITLE = "Personal Lookbook"
_MAX_LINKED_ITEMS = 20
_OCCASION_TAGS = frozenset(OCCASION_TAGS)
_SEASON_TAGS = frozenset(SEASON_TAGS)
_STYLE_TAGS = frozenset(STYLE_TAGS)


@dataclass(frozen=True)
class PrivateImageSnapshot:
    asset_id: UUID
    mime_type: str
    width: int | None
    height: int | None
    url: str
    expires_at: datetime


@dataclass(frozen=True)
class LookbookSourceSnapshot:
    wear_log_id: UUID
    wear_date: date
    worn_at: datetime
    context: str | None
    vibe: str | None
    notes: str | None
    item_count: int
    primary_image_asset_id: UUID | None
    cover_image_asset_id: UUID | None


@dataclass(frozen=True)
class LookbookOwnedOutfitSnapshot:
    id: UUID
    item_count: int
    is_archived: bool


@dataclass(frozen=True)
class LookbookLinkedItemSnapshot:
    closet_item_id: UUID
    title: str | None
    category: str | None
    subcategory: str | None
    primary_color: str | None
    display_image: ProcessingSnapshotImage | None
    thumbnail_image: ProcessingSnapshotImage | None
    role: str | None
    sort_index: int


@dataclass(frozen=True)
class LookbookEntrySummarySnapshot:
    id: UUID
    source_kind: str
    intent: str
    status: str
    title: str | None
    caption: str | None
    notes: str | None
    occasion_tag: str | None
    season_tag: str | None
    style_tag: str | None
    primary_image: PrivateImageSnapshot | None
    linked_item_count: int
    has_linked_items: bool
    source_wear_log_id: UUID | None
    owned_outfit: LookbookOwnedOutfitSnapshot | None
    source_snapshot: LookbookSourceSnapshot | None
    published_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LookbookEntryDetailSnapshot(LookbookEntrySummarySnapshot):
    linked_items: list[LookbookLinkedItemSnapshot]


@dataclass(frozen=True)
class RequestedLinkedItem:
    closet_item_id: UUID
    role: str | None
    sort_index: int


class InvalidLookbookEntryCursorError(ValueError):
    pass


class LookbookService:
    def __init__(
        self,
        *,
        session: Session,
        repository: LookbookRepository,
        storage: ObjectStorageClient,
    ) -> None:
        self.session = session
        self.repository = repository
        self.storage = storage
        self.wear_repository = WearRepository(session)

    def list_entries(
        self,
        *,
        user_id: UUID,
        cursor: str | None,
        limit: int,
        status: str | None,
        source_kind: str | None,
        intent: str | None,
        occasion_tag: str | None,
        season_tag: str | None,
        style_tag: str | None,
        has_linked_items: bool | None,
        include_archived: bool,
    ) -> tuple[list[LookbookEntrySummarySnapshot], str | None]:
        cursor_updated_at, cursor_created_at, cursor_entry_id = decode_entry_cursor(
            cursor,
            error_cls=InvalidLookbookEntryCursorError,
        )
        rows = self.repository.list_entries_for_user(
            user_id=user_id,
            limit=limit + 1,
            cursor_updated_at=cursor_updated_at,
            cursor_created_at=cursor_created_at,
            cursor_entry_id=cursor_entry_id,
            status=LookbookEntryStatus(status) if status is not None else None,
            source_kind=(
                LookbookEntrySourceKind(source_kind) if source_kind is not None else None
            ),
            intent=LookbookEntryIntent(intent) if intent is not None else None,
            occasion_tag=self._normalize_optional_tag_filter(
                occasion_tag,
                allowed_values=_OCCASION_TAGS,
                field_name="occasion_tag",
            ),
            season_tag=self._normalize_optional_tag_filter(
                season_tag,
                allowed_values=_SEASON_TAGS,
                field_name="season_tag",
            ),
            style_tag=self._normalize_optional_tag_filter(
                style_tag,
                allowed_values=_STYLE_TAGS,
                field_name="style_tag",
            ),
            has_linked_items=has_linked_items,
            include_archived=include_archived,
        )
        has_more = len(rows) > limit
        visible = rows[:limit]
        items = [self._build_entry_summary(user_id=user_id, entry=row) for row in visible]
        next_cursor = (
            encode_entry_cursor(
                updated_at=visible[-1].updated_at,
                created_at=visible[-1].created_at,
                entry_id=visible[-1].id,
            )
            if has_more and visible
            else None
        )
        return items, next_cursor

    def get_entry_detail(
        self,
        *,
        entry_id: UUID,
        user_id: UUID,
    ) -> LookbookEntryDetailSnapshot:
        entry = self._get_entry_or_raise(entry_id=entry_id, user_id=user_id)
        return self._build_entry_detail(user_id=user_id, entry=entry)

    def create_gallery_entry(
        self,
        *,
        user_id: UUID,
        intent: str,
        status: str,
        title: str | None,
        caption: str | None,
        notes: str | None,
        occasion_tag: str | None,
        season_tag: str | None,
        style_tag: str | None,
        primary_image_asset_id: UUID,
        linked_items: list[dict[str, object]],
    ) -> LookbookEntryDetailSnapshot:
        lookbook = self._get_or_create_default_lookbook(user_id=user_id)
        asset = self.repository.get_media_asset_for_user(
            asset_id=primary_image_asset_id,
            user_id=user_id,
        )
        if asset is None:
            raise LookbookError(404, "Lookbook image asset not found.")
        if not asset.mime_type.startswith("image/"):
            raise LookbookError(422, "Lookbook entries require an image asset.")

        resolved_status = LookbookEntryStatus(status)
        self._validate_publishability(status=resolved_status, title=title)
        normalized_items = self._normalize_linked_items(user_id=user_id, items=linked_items)
        owned_outfit_id = self._create_owned_outfit_for_gallery_entry(
            user_id=user_id,
            title=title,
            notes=notes,
            occasion_tag=occasion_tag,
            season_tag=season_tag,
            linked_items=normalized_items,
        )
        entry = self.repository.create_entry(
            lookbook_id=lookbook.id,
            source_kind=LookbookEntrySourceKind.GALLERY_PHOTO,
            intent=LookbookEntryIntent(intent),
            status=resolved_status,
            title=title,
            caption=caption,
            notes=notes,
            occasion_tag=occasion_tag,
            season_tag=season_tag,
            style_tag=style_tag,
            primary_image_asset_id=asset.id,
            source_wear_log_id=None,
            owned_outfit_id=owned_outfit_id,
            source_snapshot_json=None,
            published_at=utcnow() if resolved_status == LookbookEntryStatus.PUBLISHED else None,
        )
        self._touch_lookbook(lookbook)
        self.session.commit()
        return self.get_entry_detail(entry_id=entry.id, user_id=user_id)

    def create_wear_log_entry(
        self,
        *,
        user_id: UUID,
        source_wear_log_id: UUID,
        status: str,
        title: str | None,
        caption: str | None,
        notes: str | None,
        occasion_tag: str | None,
        season_tag: str | None,
        style_tag: str | None,
    ) -> LookbookEntryDetailSnapshot:
        existing = self.repository.get_entry_for_wear_log(
            source_wear_log_id=source_wear_log_id,
            user_id=user_id,
            include_archived=False,
        )
        if existing is not None:
            raise LookbookError(409, "This daily log is already saved to the lookbook.")

        lookbook = self._get_or_create_default_lookbook(user_id=user_id)
        wear_detail = self._wear_service().get_wear_log_detail(
            wear_log_id=source_wear_log_id,
            user_id=user_id,
        )
        if wear_detail.archived_at is not None:
            raise LookbookError(409, "Archived daily logs cannot be saved to the lookbook.")
        if not wear_detail.is_confirmed or wear_detail.status != "confirmed":
            raise LookbookError(409, "Only confirmed daily logs can be saved to the lookbook.")

        primary_image_asset_id = self._resolve_primary_image_asset_id_from_wear_log(wear_detail)
        if primary_image_asset_id is None:
            raise LookbookError(409, "This daily log does not have a usable lookbook image.")

        resolved_status = LookbookEntryStatus(status)
        self._validate_publishability(status=resolved_status, title=title)
        outfit = self._outfit_service().create_outfit_from_wear_log(
            wear_log_id=source_wear_log_id,
            user_id=user_id,
            title=title,
            notes=notes,
            occasion=self._map_occasion_tag_to_outfit_context(occasion_tag),
            season=self._map_season_tag_to_outfit_season(season_tag),
            is_favorite=False,
            commit=False,
        )
        entry = self.repository.create_entry(
            lookbook_id=lookbook.id,
            source_kind=LookbookEntrySourceKind.WEAR_LOG,
            intent=LookbookEntryIntent.LOGGED,
            status=resolved_status,
            title=title,
            caption=caption,
            notes=notes,
            occasion_tag=occasion_tag,
            season_tag=season_tag,
            style_tag=style_tag,
            primary_image_asset_id=primary_image_asset_id,
            source_wear_log_id=source_wear_log_id,
            owned_outfit_id=outfit.id,
            source_snapshot_json=self._build_source_snapshot_json(wear_detail),
            published_at=utcnow() if resolved_status == LookbookEntryStatus.PUBLISHED else None,
        )
        self._touch_lookbook(lookbook)
        self.session.commit()
        return self.get_entry_detail(entry_id=entry.id, user_id=user_id)

    def update_entry(
        self,
        *,
        entry_id: UUID,
        user_id: UUID,
        title: str | None,
        caption: str | None,
        notes: str | None,
        occasion_tag: str | None,
        season_tag: str | None,
        style_tag: str | None,
        status: str | None,
        primary_image_asset_id: UUID | None,
        linked_items: list[dict[str, object]] | None,
        field_names: set[str],
    ) -> LookbookEntryDetailSnapshot:
        entry = self._get_entry_or_raise(entry_id=entry_id, user_id=user_id)
        self._validate_mutable_entry(entry)
        if not field_names:
            return self.get_entry_detail(entry_id=entry.id, user_id=user_id)

        next_title = title if "title" in field_names else entry.title
        next_status = (
            LookbookEntryStatus(status) if "status" in field_names and status is not None else entry.status
        )
        self._validate_publishability(status=next_status, title=next_title)

        if "title" in field_names:
            entry.title = title
        if "caption" in field_names:
            entry.caption = caption
        if "notes" in field_names:
            entry.notes = notes
        if "occasion_tag" in field_names:
            entry.occasion_tag = occasion_tag
        if "season_tag" in field_names:
            entry.season_tag = season_tag
        if "style_tag" in field_names:
            entry.style_tag = style_tag
        if "status" in field_names:
            if status is None:
                raise LookbookError(422, "status cannot be null.")
            next_resolved_status = LookbookEntryStatus(status)
            if entry.status != next_resolved_status:
                previous_published_at = entry.published_at
                entry.status = next_resolved_status
                if entry.status == LookbookEntryStatus.PUBLISHED:
                    entry.published_at = previous_published_at or utcnow()
                else:
                    entry.published_at = None
        if "primary_image_asset_id" in field_names:
            if primary_image_asset_id is None:
                raise LookbookError(422, "primary_image_asset_id cannot be null.")
            asset = self.repository.get_media_asset_for_user(
                asset_id=primary_image_asset_id,
                user_id=user_id,
            )
            if asset is None:
                raise LookbookError(404, "Lookbook image asset not found.")
            if not asset.mime_type.startswith("image/"):
                raise LookbookError(422, "Lookbook entries require an image asset.")
            entry.image_asset_id = asset.id

        if "linked_items" in field_names:
            if linked_items is None:
                raise LookbookError(422, "linked_items cannot be null.")
            normalized_items = self._normalize_linked_items(user_id=user_id, items=linked_items)
            self._sync_owned_outfit(
                entry=entry,
                user_id=user_id,
                linked_items=normalized_items,
                title=entry.title,
                notes=entry.notes,
                occasion_tag=entry.occasion_tag,
                season_tag=entry.season_tag,
            )
        elif entry.owned_outfit_id is not None and field_names.intersection(
            {"title", "notes", "occasion_tag", "season_tag"}
        ):
            self._update_owned_outfit_metadata(
                owned_outfit_id=entry.owned_outfit_id,
                user_id=user_id,
                title=entry.title,
                notes=entry.notes,
                occasion_tag=entry.occasion_tag,
                season_tag=entry.season_tag,
            )

        self._touch_lookbook_by_entry(entry)
        self.session.commit()
        return self.get_entry_detail(entry_id=entry.id, user_id=user_id)

    def archive_entry(self, *, entry_id: UUID, user_id: UUID) -> None:
        entry = self._get_entry_or_raise(entry_id=entry_id, user_id=user_id)
        if entry.archived_at is not None:
            return
        entry.archived_at = utcnow()
        if entry.owned_outfit_id is not None:
            self._archive_owned_outfit(owned_outfit_id=entry.owned_outfit_id, user_id=user_id)
        self._touch_lookbook_by_entry(entry)
        self.session.commit()

    def delete_entry(self, *, entry_id: UUID, user_id: UUID) -> None:
        entry = self._get_entry_or_raise(entry_id=entry_id, user_id=user_id)
        if entry.owned_outfit_id is not None:
            self._archive_owned_outfit(owned_outfit_id=entry.owned_outfit_id, user_id=user_id)
        self._touch_lookbook_by_entry(entry)
        self.repository.delete_entry(entry=entry)
        self.session.commit()

    def create_wear_log_from_entry(
        self,
        *,
        entry_id: UUID,
        user_id: UUID,
        wear_date: date | None,
        worn_at: datetime | None,
        timezone_name: str | None,
        context: str | None,
        notes: str | None,
    ) -> WearLogDetailView:
        entry = self._get_entry_or_raise(entry_id=entry_id, user_id=user_id)
        if entry.archived_at is not None:
            raise LookbookError(409, "Archived lookbook entries cannot start a wear log.")
        if entry.owned_outfit_id is None:
            raise LookbookError(409, "Link closet items before logging this look.")
        outfit = self.wear_repository.get_outfit_for_user(
            outfit_id=entry.owned_outfit_id,
            user_id=user_id,
        )
        if outfit is None:
            raise LookbookError(409, "This look no longer has a usable outfit for wear logging.")
        if outfit.archived_at is not None:
            raise LookbookError(409, "Archived linked outfits cannot be used for wear logging.")

        reference_datetime = worn_at or datetime.now(UTC)
        resolved_wear_date = wear_date or reference_datetime.date()
        return self._wear_service().create_wear_log(
            user_id=user_id,
            wear_date=resolved_wear_date,
            worn_at=worn_at,
            captured_at=None,
            timezone_name=timezone_name,
            mode="saved_outfit",
            context=context or self._map_occasion_tag_to_outfit_context(entry.occasion_tag),
            vibe=entry.style_tag,
            notes=notes or entry.notes or entry.caption,
            items=None,
            outfit_id=entry.owned_outfit_id,
        )

    def _get_or_create_default_lookbook(self, *, user_id: UUID) -> Lookbook:
        return self.repository.get_or_create_default_lookbook(
            user_id=user_id,
            title=_LOOKBOOK_DEFAULT_TITLE,
            description=None,
        )

    def _get_entry_or_raise(self, *, entry_id: UUID, user_id: UUID) -> LookbookEntry:
        entry = self.repository.get_entry_for_user(entry_id=entry_id, user_id=user_id)
        if entry is None:
            raise LookbookError(404, "Lookbook entry not found.")
        return entry

    def _build_entry_summary(
        self,
        *,
        user_id: UUID,
        entry: LookbookEntry,
    ) -> LookbookEntrySummarySnapshot:
        primary_image = (
            self._build_private_image_snapshot_for_asset_id(entry.image_asset_id)
            if entry.image_asset_id is not None
            else None
        )
        outfit_detail = self._get_owned_outfit_detail(entry=entry, user_id=user_id)
        fallback_owned_outfit = None
        fallback_linked_item_count = 0
        if outfit_detail is None and entry.owned_outfit_id is not None:
            fallback_owned_outfit = self.wear_repository.get_outfit_for_user(
                outfit_id=entry.owned_outfit_id,
                user_id=user_id,
            )
            if fallback_owned_outfit is not None:
                fallback_linked_item_count = len(
                    self.wear_repository.list_outfit_items(outfit_id=fallback_owned_outfit.id)
                )
        return LookbookEntrySummarySnapshot(
            id=entry.id,
            source_kind=entry.source_kind.value,
            intent=entry.intent.value,
            status=entry.status.value,
            title=entry.title,
            caption=entry.caption,
            notes=entry.notes,
            occasion_tag=entry.occasion_tag,
            season_tag=entry.season_tag,
            style_tag=entry.style_tag,
            primary_image=primary_image,
            linked_item_count=(
                outfit_detail.item_count if outfit_detail is not None else fallback_linked_item_count
            ),
            has_linked_items=(
                outfit_detail.item_count > 0
                if outfit_detail is not None
                else fallback_linked_item_count > 0
            ),
            source_wear_log_id=entry.source_wear_log_id,
            owned_outfit=(
                LookbookOwnedOutfitSnapshot(
                    id=outfit_detail.id,
                    item_count=outfit_detail.item_count,
                    is_archived=outfit_detail.is_archived,
                )
                if outfit_detail is not None
                else (
                    LookbookOwnedOutfitSnapshot(
                        id=fallback_owned_outfit.id,
                        item_count=fallback_linked_item_count,
                        is_archived=fallback_owned_outfit.archived_at is not None,
                    )
                    if fallback_owned_outfit is not None
                    else None
                )
            ),
            source_snapshot=self._build_source_snapshot(entry.source_snapshot_json),
            published_at=normalize_optional_datetime(entry.published_at),
            archived_at=normalize_optional_datetime(entry.archived_at),
            created_at=normalize_optional_datetime(entry.created_at),
            updated_at=normalize_optional_datetime(entry.updated_at),
        )

    def _build_entry_detail(
        self,
        *,
        user_id: UUID,
        entry: LookbookEntry,
    ) -> LookbookEntryDetailSnapshot:
        summary = self._build_entry_summary(user_id=user_id, entry=entry)
        outfit_detail = self._get_owned_outfit_detail(entry=entry, user_id=user_id)
        linked_items = (
            [self._build_linked_item_snapshot(item) for item in outfit_detail.items]
            if outfit_detail is not None
            else []
        )
        return LookbookEntryDetailSnapshot(**summary.__dict__, linked_items=linked_items)

    def _build_linked_item_snapshot(
        self,
        item: Any,
    ) -> LookbookLinkedItemSnapshot:
        return LookbookLinkedItemSnapshot(
            closet_item_id=item.closet_item_id,
            title=item.title,
            category=item.category,
            subcategory=item.subcategory,
            primary_color=item.primary_color,
            display_image=item.display_image,
            thumbnail_image=item.thumbnail_image,
            role=item.role,
            sort_index=item.sort_index,
        )

    def _build_source_snapshot(
        self,
        payload: dict[str, object] | None,
    ) -> LookbookSourceSnapshot | None:
        if payload is None:
            return None
        try:
            wear_log_id_raw = payload.get("wear_log_id")
            wear_date_raw = payload.get("wear_date")
            worn_at_raw = payload.get("worn_at")
            if not isinstance(wear_log_id_raw, str) or not isinstance(wear_date_raw, str) or not isinstance(
                worn_at_raw, str
            ):
                return None
            return LookbookSourceSnapshot(
                wear_log_id=UUID(wear_log_id_raw),
                wear_date=date.fromisoformat(wear_date_raw),
                worn_at=normalize_optional_datetime(
                    datetime.fromisoformat(worn_at_raw.replace("Z", "+00:00"))
                ),
                context=payload.get("context") if isinstance(payload.get("context"), str) else None,
                vibe=payload.get("vibe") if isinstance(payload.get("vibe"), str) else None,
                notes=payload.get("notes") if isinstance(payload.get("notes"), str) else None,
                item_count=int(payload.get("item_count") or 0),
                primary_image_asset_id=(
                    UUID(payload["primary_image_asset_id"])
                    if isinstance(payload.get("primary_image_asset_id"), str)
                    else None
                ),
                cover_image_asset_id=(
                    UUID(payload["cover_image_asset_id"])
                    if isinstance(payload.get("cover_image_asset_id"), str)
                    else None
                ),
            )
        except (TypeError, ValueError):
            return None

    def _build_source_snapshot_json(self, wear_detail: WearLogDetailView) -> dict[str, object]:
        primary_image_asset_id = wear_detail.primary_photo.asset_id if wear_detail.primary_photo else None
        cover_image_asset_id = wear_detail.cover_image.asset_id if wear_detail.cover_image else None
        return {
            "wear_log_id": str(wear_detail.id),
            "wear_date": wear_detail.wear_date.isoformat(),
            "worn_at": wear_detail.worn_at.isoformat().replace("+00:00", "Z"),
            "context": wear_detail.context,
            "vibe": wear_detail.vibe,
            "notes": wear_detail.notes,
            "item_count": wear_detail.item_count,
            "primary_image_asset_id": str(primary_image_asset_id) if primary_image_asset_id is not None else None,
            "cover_image_asset_id": str(cover_image_asset_id) if cover_image_asset_id is not None else None,
        }

    def _resolve_primary_image_asset_id_from_wear_log(
        self,
        wear_detail: WearLogDetailView,
    ) -> UUID | None:
        if wear_detail.primary_photo is not None:
            return wear_detail.primary_photo.asset_id
        if wear_detail.cover_image is not None:
            return wear_detail.cover_image.asset_id
        for item in wear_detail.items:
            if item.display_image is not None:
                return item.display_image.asset_id
            if item.thumbnail_image is not None:
                return item.thumbnail_image.asset_id
        return None

    def _get_owned_outfit_detail(
        self,
        *,
        entry: LookbookEntry,
        user_id: UUID,
    ) -> OutfitDetailView | None:
        if entry.owned_outfit_id is None:
            return None
        try:
            return self._outfit_service().get_outfit_detail(
                outfit_id=entry.owned_outfit_id,
                user_id=user_id,
            )
        except Exception:
            logger.warning(
                "Failed to hydrate owned outfit for lookbook entry.",
                extra={
                    "entry_id": str(entry.id),
                    "owned_outfit_id": str(entry.owned_outfit_id),
                },
                exc_info=True,
            )
            return None

    def _create_owned_outfit_for_gallery_entry(
        self,
        *,
        user_id: UUID,
        title: str | None,
        notes: str | None,
        occasion_tag: str | None,
        season_tag: str | None,
        linked_items: list[RequestedLinkedItem],
    ) -> UUID | None:
        if not linked_items:
            return None
        outfit = self._outfit_service().create_outfit(
            user_id=user_id,
            title=title,
            notes=notes,
            occasion=self._map_occasion_tag_to_outfit_context(occasion_tag),
            season=self._map_season_tag_to_outfit_season(season_tag),
            is_favorite=False,
            commit=False,
            items=[
                {
                    "closet_item_id": item.closet_item_id,
                    "role": item.role,
                    "layer_index": None,
                    "sort_index": item.sort_index,
                    "is_optional": False,
                }
                for item in linked_items
            ],
        )
        return outfit.id

    def _sync_owned_outfit(
        self,
        *,
        entry: LookbookEntry,
        user_id: UUID,
        linked_items: list[RequestedLinkedItem],
        title: str | None,
        notes: str | None,
        occasion_tag: str | None,
        season_tag: str | None,
    ) -> None:
        if entry.source_kind == LookbookEntrySourceKind.WEAR_LOG and not linked_items:
            raise LookbookError(422, "Wear-log looks must keep at least one linked closet item.")

        if not linked_items:
            if entry.owned_outfit_id is not None:
                self._archive_owned_outfit(owned_outfit_id=entry.owned_outfit_id, user_id=user_id)
                entry.owned_outfit_id = None
            return

        payload = [
            {
                "closet_item_id": item.closet_item_id,
                "role": item.role,
                "layer_index": None,
                "sort_index": item.sort_index,
                "is_optional": False,
            }
            for item in linked_items
        ]
        if entry.owned_outfit_id is None:
            outfit = self._outfit_service().create_outfit(
                user_id=user_id,
                title=title,
                notes=notes,
                occasion=self._map_occasion_tag_to_outfit_context(occasion_tag),
                season=self._map_season_tag_to_outfit_season(season_tag),
                is_favorite=False,
                commit=False,
                items=payload,
            )
            entry.owned_outfit_id = outfit.id
            return

        self._outfit_service().update_outfit(
            outfit_id=entry.owned_outfit_id,
            user_id=user_id,
            title=title,
            notes=notes,
            occasion=self._map_occasion_tag_to_outfit_context(occasion_tag),
            season=self._map_season_tag_to_outfit_season(season_tag),
            is_favorite=False,
            items=payload,
            commit=False,
            field_names={"title", "notes", "occasion", "season", "items", "is_favorite"},
        )

    def _update_owned_outfit_metadata(
        self,
        *,
        owned_outfit_id: UUID,
        user_id: UUID,
        title: str | None,
        notes: str | None,
        occasion_tag: str | None,
        season_tag: str | None,
    ) -> None:
        self._outfit_service().update_outfit(
            outfit_id=owned_outfit_id,
            user_id=user_id,
            title=title,
            notes=notes,
            occasion=self._map_occasion_tag_to_outfit_context(occasion_tag),
            season=self._map_season_tag_to_outfit_season(season_tag),
            is_favorite=False,
            items=None,
            commit=False,
            field_names={"title", "notes", "occasion", "season", "is_favorite"},
        )

    def _archive_owned_outfit(self, *, owned_outfit_id: UUID, user_id: UUID) -> None:
        self._outfit_service().archive_outfit(
            outfit_id=owned_outfit_id,
            user_id=user_id,
            commit=False,
        )

    def _normalize_linked_items(
        self,
        *,
        user_id: UUID,
        items: list[dict[str, object]],
    ) -> list[RequestedLinkedItem]:
        if len(items) > _MAX_LINKED_ITEMS:
            raise LookbookError(422, f"A lookbook entry can link at most {_MAX_LINKED_ITEMS} items.")

        seen_item_ids: set[UUID] = set()
        sortable_items: list[tuple[int, int, RequestedLinkedItem]] = []

        for position, item in enumerate(items):
            closet_item_id = item.get("closet_item_id")
            if not isinstance(closet_item_id, UUID):
                raise LookbookError(422, "Each linked item requires a valid closet_item_id.")
            if closet_item_id in seen_item_ids:
                raise LookbookError(422, "A closet item can appear only once in a lookbook entry.")
            seen_item_ids.add(closet_item_id)
            provided_sort_index = item.get("sort_index")
            role_raw = item.get("role")
            role = str(role_raw) if isinstance(role_raw, str) else None
            sortable_items.append(
                (
                    provided_sort_index if isinstance(provided_sort_index, int) else position,
                    position,
                    RequestedLinkedItem(
                        closet_item_id=closet_item_id,
                        role=role,
                        sort_index=0,
                    ),
                )
            )

        normalized_items: list[RequestedLinkedItem] = []
        for final_index, (_, _, requested_item) in enumerate(sorted(sortable_items, key=lambda value: value[:2])):
            normalized_items.append(
                RequestedLinkedItem(
                    closet_item_id=requested_item.closet_item_id,
                    role=requested_item.role,
                    sort_index=final_index,
                )
            )

        confirmed_items = self.wear_repository.get_confirmed_closet_items_with_projections_for_user(
            item_ids=[item.closet_item_id for item in normalized_items],
            user_id=user_id,
        )
        if len(confirmed_items) != len(normalized_items):
            raise LookbookError(404, "One or more linked closet items could not be found.")
        return normalized_items

    def _validate_publishability(
        self,
        *,
        status: LookbookEntryStatus,
        title: str | None,
    ) -> None:
        if status == LookbookEntryStatus.PUBLISHED and title is None:
            raise LookbookError(422, "A published lookbook entry requires a title.")

    def _validate_mutable_entry(self, entry: LookbookEntry) -> None:
        if entry.archived_at is not None:
            raise LookbookError(409, "Archived lookbook entries cannot be edited.")

    def _touch_lookbook(self, lookbook: Lookbook) -> None:
        lookbook.updated_at = utcnow()

    def _touch_lookbook_by_entry(self, entry: LookbookEntry) -> None:
        lookbook = self.session.get(Lookbook, entry.lookbook_id)
        if lookbook is not None:
            self._touch_lookbook(lookbook)

    def _build_private_image_snapshot_for_asset_id(
        self,
        asset_id: UUID | None,
    ) -> PrivateImageSnapshot | None:
        if asset_id is None:
            return None
        asset = self.repository.get_media_assets_by_ids(asset_ids=[asset_id]).get(asset_id)
        if asset is None:
            return None
        return self._try_build_private_image_snapshot(asset)

    def _build_private_image_snapshot(self, asset: MediaAsset) -> PrivateImageSnapshot:
        presigned_download = self.storage.generate_presigned_download(
            bucket=asset.bucket,
            key=asset.key,
            expires_in_seconds=settings.closet_media_download_ttl_seconds,
        )
        return PrivateImageSnapshot(
            asset_id=asset.id,
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            url=presigned_download.url,
            expires_at=normalize_optional_datetime(presigned_download.expires_at),
        )

    def _try_build_private_image_snapshot(self, asset: MediaAsset) -> PrivateImageSnapshot | None:
        try:
            return self._build_private_image_snapshot(asset)
        except Exception:
            logger.warning(
                "Failed to generate lookbook image download URL.",
                extra={
                    "asset_id": str(asset.id),
                    "bucket": asset.bucket,
                    "key": asset.key,
                },
                exc_info=True,
            )
            return None

    def _normalize_optional_tag_filter(
        self,
        value: str | None,
        *,
        allowed_values: frozenset[str],
        field_name: str,
    ) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in allowed_values:
            allowed = ", ".join(sorted(allowed_values))
            raise LookbookError(422, f"{field_name} must be one of: {allowed}.")
        return normalized

    def _map_occasion_tag_to_outfit_context(self, value: str | None) -> str | None:
        if value is None:
            return None
        return {
            "everyday": "casual",
            "work": "work",
            "business": "work",
            "formal": "event",
            "evening": "event",
            "event": "event",
            "active": "gym",
            "travel": "travel",
            "lounge": "lounge",
            "vacation": "travel",
        }.get(value)

    def _map_season_tag_to_outfit_season(self, value: str | None) -> str | None:
        if value in {"summer", "winter"}:
            return value
        return None

    def _outfit_service(self) -> OutfitService:
        return OutfitService(
            session=self.session,
            repository=self.wear_repository,
            storage=self.storage,
        )

    def _wear_service(self) -> WearService:
        return WearService(
            session=self.session,
            repository=self.wear_repository,
            storage=self.storage,
        )


def encode_entry_cursor(
    *,
    updated_at: datetime,
    created_at: datetime,
    entry_id: UUID,
) -> str:
    payload = (
        f"{normalize_optional_datetime(updated_at).isoformat()}|"
        f"{normalize_optional_datetime(created_at).isoformat()}|"
        f"{entry_id}"
    )
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_entry_cursor(
    cursor: str | None,
    *,
    error_cls: type[ValueError],
) -> tuple[datetime | None, datetime | None, UUID | None]:
    if cursor is None:
        return None, None, None
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        updated_at_raw, created_at_raw, entry_id_raw = decoded.split("|", 2)
        return (
            datetime.fromisoformat(updated_at_raw),
            datetime.fromisoformat(created_at_raw),
            UUID(entry_id_raw),
        )
    except (TypeError, ValueError) as exc:
        raise error_cls("Invalid cursor.") from exc


def normalize_optional_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
