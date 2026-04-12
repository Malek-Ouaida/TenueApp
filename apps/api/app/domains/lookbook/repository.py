from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.closet.models import MediaAsset, MediaAssetSourceKind
from app.domains.lookbook.models import (
    Lookbook,
    LookbookEntry,
    LookbookEntryIntent,
    LookbookEntrySourceKind,
    LookbookEntryStatus,
    LookbookEntryType,
    LookbookUploadIntent,
    LookbookUploadIntentStatus,
)


class LookbookRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_default_lookbook_for_user(self, *, user_id: UUID) -> Lookbook | None:
        statement = (
            select(Lookbook)
            .where(
                Lookbook.user_id == user_id,
                Lookbook.is_default.is_(True),
            )
            .order_by(Lookbook.updated_at.desc(), Lookbook.id.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def create_lookbook(
        self,
        *,
        user_id: UUID,
        title: str,
        description: str | None,
        is_default: bool,
    ) -> Lookbook:
        lookbook = Lookbook(
            user_id=user_id,
            title=title,
            description=description,
            is_default=is_default,
        )
        self.session.add(lookbook)
        self.session.flush()
        return lookbook

    def get_or_create_default_lookbook(
        self,
        *,
        user_id: UUID,
        title: str,
        description: str | None,
    ) -> Lookbook:
        lookbook = self.get_default_lookbook_for_user(user_id=user_id)
        if lookbook is not None:
            return lookbook

        try:
            return self.create_lookbook(
                user_id=user_id,
                title=title,
                description=description,
                is_default=True,
            )
        except IntegrityError:
            self.session.rollback()
            lookbook = self.get_default_lookbook_for_user(user_id=user_id)
            if lookbook is not None:
                return lookbook
            raise

    def create_entry(
        self,
        *,
        lookbook_id: UUID,
        source_kind: LookbookEntrySourceKind,
        intent: LookbookEntryIntent,
        status: LookbookEntryStatus,
        title: str | None,
        caption: str | None,
        notes: str | None,
        occasion_tag: str | None,
        season_tag: str | None,
        style_tag: str | None,
        primary_image_asset_id: UUID,
        source_wear_log_id: UUID | None,
        owned_outfit_id: UUID | None,
        source_snapshot_json: dict[str, object] | None,
        published_at: datetime | None,
    ) -> LookbookEntry:
        entry = LookbookEntry(
            lookbook_id=lookbook_id,
            entry_type=LookbookEntryType.IMAGE,
            outfit_id=None,
            image_asset_id=primary_image_asset_id,
            caption=caption,
            note_text=None,
            sort_index=0,
            source_kind=source_kind,
            intent=intent,
            status=status,
            title=title,
            notes=notes,
            occasion_tag=occasion_tag,
            season_tag=season_tag,
            style_tag=style_tag,
            source_wear_log_id=source_wear_log_id,
            owned_outfit_id=owned_outfit_id,
            source_snapshot_json=source_snapshot_json,
            published_at=published_at,
            archived_at=None,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_entries_for_user(
        self,
        *,
        user_id: UUID,
        cursor_updated_at: datetime | None,
        cursor_created_at: datetime | None,
        cursor_entry_id: UUID | None,
        limit: int,
        status: LookbookEntryStatus | None,
        source_kind: LookbookEntrySourceKind | None,
        intent: LookbookEntryIntent | None,
        occasion_tag: str | None,
        season_tag: str | None,
        style_tag: str | None,
        has_linked_items: bool | None,
        include_archived: bool,
    ) -> list[LookbookEntry]:
        default_lookbook = self.get_default_lookbook_for_user(user_id=user_id)
        if default_lookbook is None:
            return []

        statement = select(LookbookEntry).where(LookbookEntry.lookbook_id == default_lookbook.id)

        if not include_archived:
            statement = statement.where(LookbookEntry.archived_at.is_(None))
        if status is not None:
            statement = statement.where(LookbookEntry.status == status)
        if source_kind is not None:
            statement = statement.where(LookbookEntry.source_kind == source_kind)
        if intent is not None:
            statement = statement.where(LookbookEntry.intent == intent)
        if occasion_tag is not None:
            statement = statement.where(LookbookEntry.occasion_tag == occasion_tag)
        if season_tag is not None:
            statement = statement.where(LookbookEntry.season_tag == season_tag)
        if style_tag is not None:
            statement = statement.where(LookbookEntry.style_tag == style_tag)
        if has_linked_items is not None:
            if has_linked_items:
                statement = statement.where(LookbookEntry.owned_outfit_id.is_not(None))
            else:
                statement = statement.where(LookbookEntry.owned_outfit_id.is_(None))
        if (
            cursor_updated_at is not None
            and cursor_created_at is not None
            and cursor_entry_id is not None
        ):
            statement = statement.where(
                or_(
                    LookbookEntry.updated_at < cursor_updated_at,
                    and_(
                        LookbookEntry.updated_at == cursor_updated_at,
                        LookbookEntry.created_at < cursor_created_at,
                    ),
                    and_(
                        LookbookEntry.updated_at == cursor_updated_at,
                        LookbookEntry.created_at == cursor_created_at,
                        LookbookEntry.id < cursor_entry_id,
                    ),
                )
            )

        statement = (
            statement.order_by(
                LookbookEntry.updated_at.desc(),
                LookbookEntry.created_at.desc(),
                LookbookEntry.id.desc(),
            )
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars())

    def get_entry_for_user(self, *, entry_id: UUID, user_id: UUID) -> LookbookEntry | None:
        statement = (
            select(LookbookEntry)
            .join(Lookbook, Lookbook.id == LookbookEntry.lookbook_id)
            .where(
                LookbookEntry.id == entry_id,
                Lookbook.user_id == user_id,
                Lookbook.is_default.is_(True),
            )
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_entry_for_wear_log(
        self,
        *,
        source_wear_log_id: UUID,
        user_id: UUID,
        include_archived: bool,
    ) -> LookbookEntry | None:
        statement = (
            select(LookbookEntry)
            .join(Lookbook, Lookbook.id == LookbookEntry.lookbook_id)
            .where(
                Lookbook.user_id == user_id,
                Lookbook.is_default.is_(True),
                LookbookEntry.source_wear_log_id == source_wear_log_id,
            )
            .order_by(LookbookEntry.updated_at.desc(), LookbookEntry.id.desc())
            .limit(1)
        )
        if not include_archived:
            statement = statement.where(LookbookEntry.archived_at.is_(None))
        return self.session.execute(statement).scalar_one_or_none()

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

    def clear_expired_upload_intents(self, *, user_id: UUID) -> None:
        self.session.execute(
            delete(LookbookUploadIntent).where(
                LookbookUploadIntent.user_id == user_id,
                LookbookUploadIntent.status.in_(
                    (
                        LookbookUploadIntentStatus.EXPIRED,
                        LookbookUploadIntentStatus.FAILED,
                    )
                ),
            )
        )
        self.session.flush()

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
            MediaAsset.id == asset_id,
            MediaAsset.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_media_assets_by_ids(self, *, asset_ids: list[UUID]) -> dict[UUID, MediaAsset]:
        if not asset_ids:
            return {}

        statement = select(MediaAsset).where(MediaAsset.id.in_(asset_ids))
        return {asset.id: asset for asset in self.session.execute(statement).scalars()}
