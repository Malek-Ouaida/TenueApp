from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.domains.closet.models import (
    ClosetItemImage,
    ClosetItemImageRole,
    MediaAsset,
    MediaAssetSourceKind,
)
from app.domains.lookbook.models import (
    Lookbook,
    LookbookEntry,
    LookbookEntryType,
    LookbookUploadIntent,
    LookbookUploadIntentStatus,
)
from app.domains.wear.models import Outfit, OutfitItem


class LookbookRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_lookbook(
        self,
        *,
        user_id: UUID,
        title: str,
        description: str | None,
    ) -> Lookbook:
        lookbook = Lookbook(user_id=user_id, title=title, description=description)
        self.session.add(lookbook)
        self.session.flush()
        return lookbook

    def get_lookbook_for_user(self, *, lookbook_id: UUID, user_id: UUID) -> Lookbook | None:
        statement = select(Lookbook).where(
            Lookbook.id == lookbook_id,
            Lookbook.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_lookbooks(
        self,
        *,
        user_id: UUID,
        offset: int,
        limit: int,
    ) -> list[Lookbook]:
        statement = (
            select(Lookbook)
            .where(Lookbook.user_id == user_id)
            .order_by(Lookbook.updated_at.desc(), Lookbook.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars())

    def delete_lookbook(self, *, lookbook: Lookbook) -> None:
        self.session.execute(
            delete(LookbookUploadIntent).where(LookbookUploadIntent.lookbook_id == lookbook.id)
        )
        self.session.execute(delete(LookbookEntry).where(LookbookEntry.lookbook_id == lookbook.id))
        self.session.delete(lookbook)
        self.session.flush()

    def create_entry(
        self,
        *,
        lookbook_id: UUID,
        entry_type: LookbookEntryType,
        outfit_id: UUID | None,
        image_asset_id: UUID | None,
        caption: str | None,
        note_text: str | None,
        sort_index: int,
    ) -> LookbookEntry:
        entry = LookbookEntry(
            lookbook_id=lookbook_id,
            entry_type=entry_type,
            outfit_id=outfit_id,
            image_asset_id=image_asset_id,
            caption=caption,
            note_text=note_text,
            sort_index=sort_index,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def get_entry_for_lookbook(
        self,
        *,
        lookbook_id: UUID,
        entry_id: UUID,
    ) -> LookbookEntry | None:
        statement = select(LookbookEntry).where(
            LookbookEntry.lookbook_id == lookbook_id,
            LookbookEntry.id == entry_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_entries_for_lookbook(
        self,
        *,
        lookbook_id: UUID,
        offset: int,
        limit: int,
    ) -> list[LookbookEntry]:
        statement = (
            select(LookbookEntry)
            .where(LookbookEntry.lookbook_id == lookbook_id)
            .order_by(LookbookEntry.sort_index.asc(), LookbookEntry.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars())

    def list_all_entries_for_lookbook(self, *, lookbook_id: UUID) -> list[LookbookEntry]:
        statement = (
            select(LookbookEntry)
            .where(LookbookEntry.lookbook_id == lookbook_id)
            .order_by(LookbookEntry.sort_index.asc(), LookbookEntry.id.asc())
        )
        return list(self.session.execute(statement).scalars())

    def list_entries_for_lookbooks(
        self,
        *,
        lookbook_ids: list[UUID],
    ) -> dict[UUID, list[LookbookEntry]]:
        if not lookbook_ids:
            return {}

        statement = (
            select(LookbookEntry)
            .where(LookbookEntry.lookbook_id.in_(lookbook_ids))
            .order_by(
                LookbookEntry.lookbook_id.asc(),
                LookbookEntry.sort_index.asc(),
                LookbookEntry.id.asc(),
            )
        )
        entries_by_lookbook: dict[UUID, list[LookbookEntry]] = {}
        for entry in self.session.execute(statement).scalars():
            entries_by_lookbook.setdefault(entry.lookbook_id, []).append(entry)
        return entries_by_lookbook

    def get_next_entry_sort_index(self, *, lookbook_id: UUID) -> int:
        statement = select(func.max(LookbookEntry.sort_index)).where(
            LookbookEntry.lookbook_id == lookbook_id
        )
        current_max = self.session.execute(statement).scalar_one()
        return int(current_max) + 1 if current_max is not None else 0

    def delete_entry(self, *, entry: LookbookEntry) -> None:
        self.session.delete(entry)
        self.session.flush()

    def create_upload_intent(
        self,
        *,
        upload_intent_id: UUID,
        lookbook_id: UUID,
        user_id: UUID,
        filename: str,
        mime_type: str,
        file_size: int,
        sha256: str,
        staging_bucket: str,
        staging_key: str,
        expires_at: datetime,
    ) -> LookbookUploadIntent:
        upload_intent = LookbookUploadIntent(
            id=upload_intent_id,
            lookbook_id=lookbook_id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            sha256=sha256,
            staging_bucket=staging_bucket,
            staging_key=staging_key,
            status=LookbookUploadIntentStatus.PENDING,
            expires_at=expires_at,
        )
        self.session.add(upload_intent)
        self.session.flush()
        return upload_intent

    def get_upload_intent_for_user(
        self,
        *,
        upload_intent_id: UUID,
        user_id: UUID,
    ) -> LookbookUploadIntent | None:
        statement = select(LookbookUploadIntent).where(
            LookbookUploadIntent.id == upload_intent_id,
            LookbookUploadIntent.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def mark_upload_intent_expired(
        self,
        *,
        upload_intent: LookbookUploadIntent,
    ) -> LookbookUploadIntent:
        upload_intent.status = LookbookUploadIntentStatus.EXPIRED
        upload_intent.last_error_code = None
        upload_intent.last_error_detail = None
        self.session.flush()
        return upload_intent

    def mark_upload_intent_failed(
        self,
        *,
        upload_intent: LookbookUploadIntent,
        error_code: str,
        error_detail: str,
    ) -> LookbookUploadIntent:
        upload_intent.status = LookbookUploadIntentStatus.FAILED
        upload_intent.last_error_code = error_code
        upload_intent.last_error_detail = error_detail
        self.session.flush()
        return upload_intent

    def mark_upload_intent_finalized(
        self,
        *,
        upload_intent: LookbookUploadIntent,
        finalized_at: datetime,
    ) -> LookbookUploadIntent:
        upload_intent.status = LookbookUploadIntentStatus.FINALIZED
        upload_intent.finalized_at = finalized_at
        upload_intent.last_error_code = None
        upload_intent.last_error_detail = None
        self.session.flush()
        return upload_intent

    def create_media_asset(
        self,
        *,
        asset_id: UUID,
        user_id: UUID,
        bucket: str,
        key: str,
        mime_type: str,
        file_size: int,
        checksum: str,
        width: int | None,
        height: int | None,
        source_kind: MediaAssetSourceKind,
        is_private: bool,
    ) -> MediaAsset:
        asset = MediaAsset(
            id=asset_id,
            user_id=user_id,
            bucket=bucket,
            key=key,
            mime_type=mime_type,
            file_size=file_size,
            checksum=checksum,
            width=width,
            height=height,
            source_kind=source_kind,
            is_private=is_private,
        )
        self.session.add(asset)
        self.session.flush()
        return asset

    def get_media_asset_for_user(self, *, asset_id: UUID, user_id: UUID) -> MediaAsset | None:
        statement = select(MediaAsset).where(
            MediaAsset.id == asset_id, MediaAsset.user_id == user_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_media_assets_by_ids(self, *, asset_ids: list[UUID]) -> dict[UUID, MediaAsset]:
        if not asset_ids:
            return {}
        statement = select(MediaAsset).where(MediaAsset.id.in_(asset_ids))
        return {asset.id: asset for asset in self.session.execute(statement).scalars()}

    def get_outfit_for_user(self, *, outfit_id: UUID, user_id: UUID) -> Outfit | None:
        statement = select(Outfit).where(Outfit.id == outfit_id, Outfit.user_id == user_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_outfits_for_user(
        self,
        *,
        outfit_ids: list[UUID],
        user_id: UUID,
    ) -> dict[UUID, Outfit]:
        if not outfit_ids:
            return {}
        statement = select(Outfit).where(Outfit.user_id == user_id, Outfit.id.in_(outfit_ids))
        return {outfit.id: outfit for outfit in self.session.execute(statement).scalars()}

    def list_outfit_items_for_outfits(
        self,
        *,
        outfit_ids: list[UUID],
    ) -> dict[UUID, list[OutfitItem]]:
        if not outfit_ids:
            return {}
        statement = (
            select(OutfitItem)
            .where(OutfitItem.outfit_id.in_(outfit_ids))
            .order_by(OutfitItem.outfit_id.asc(), OutfitItem.sort_index.asc(), OutfitItem.id.asc())
        )
        items_by_outfit: dict[UUID, list[OutfitItem]] = {}
        for item in self.session.execute(statement).scalars():
            items_by_outfit.setdefault(item.outfit_id, []).append(item)
        return items_by_outfit

    def list_active_image_assets_for_items(
        self,
        *,
        closet_item_ids: list[UUID],
        roles: list[ClosetItemImageRole],
    ) -> dict[UUID, dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]]]:
        if not closet_item_ids or not roles:
            return {}

        statement = (
            select(ClosetItemImage, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ClosetItemImage.asset_id)
            .where(
                ClosetItemImage.closet_item_id.in_(closet_item_ids),
                ClosetItemImage.role.in_(roles),
                ClosetItemImage.is_active.is_(True),
            )
            .order_by(
                ClosetItemImage.closet_item_id.asc(),
                ClosetItemImage.role.asc(),
                ClosetItemImage.position.asc(),
                ClosetItemImage.created_at.desc(),
                ClosetItemImage.id.desc(),
            )
        )
        images_by_item: dict[
            UUID, dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]]
        ] = {}
        for item_image, asset in self.session.execute(statement).all():
            item_images = images_by_item.setdefault(item_image.closet_item_id, {})
            if item_image.role not in item_images:
                item_images[item_image.role] = (item_image, asset)
        return images_by_item
