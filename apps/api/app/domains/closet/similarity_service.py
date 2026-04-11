from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient
from app.domains.closet.browse_service import BrowseListItemSnapshot, build_browse_list_item_snapshot
from app.domains.closet.errors import (
    CLOSET_ITEM_NOT_FOUND,
    INVALID_LIFECYCLE_TRANSITION,
    SIMILARITY_EDGE_NOT_FOUND,
    SIMILARITY_RECOMPUTE_ALREADY_SCHEDULED,
    build_error,
)
from app.domains.closet.image_processing_service import ProcessingSnapshotImage
from app.domains.closet.models import (
    AuditActorType,
    ClosetItem,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetItemMetadataProjection,
    ClosetItemSimilarityEdge,
    ClosetJob,
    ClosetJobStatus,
    LifecycleStatus,
    MediaAsset,
    ProcessingRun,
    ProcessingRunType,
    ProcessingStatus,
    ReviewStatus,
    SimilarityDecisionStatus,
    SimilarityType,
    utcnow,
)
from app.domains.closet.repository import (
    ClosetJobRepository,
    ClosetRepository,
    canonicalize_similarity_pair,
)
from app.domains.closet.similarity import ComparableItem, compute_similarity


@dataclass(frozen=True)
class SimilaritySignalSnapshot:
    code: str
    label: str
    contribution: float
    metadata: dict[str, Any] | None


@dataclass(frozen=True)
class SimilarityEdgeSnapshot:
    edge_id: UUID
    item_a_id: UUID
    item_b_id: UUID
    label: str
    similarity_type: str
    decision_status: str
    score: float
    signals: list[SimilaritySignalSnapshot]


@dataclass(frozen=True)
class SimilarityListItemSnapshot:
    edge_id: UUID
    label: str
    similarity_type: str
    decision_status: str
    score: float
    signals: list[SimilaritySignalSnapshot]
    other_item: BrowseListItemSnapshot


@dataclass(frozen=True)
class SimilarityListSnapshot:
    item_id: UUID
    similarity_status: str
    latest_run: ProcessingRun | None
    items: list[SimilarityListItemSnapshot]


@dataclass(frozen=True)
class _ComparableProjection:
    comparable_item: ComparableItem
    issue: str | None


class ClosetSimilarityService:
    def __init__(
        self,
        *,
        session: Session,
        repository: ClosetRepository,
        job_repository: ClosetJobRepository,
        storage: ObjectStorageClient,
    ) -> None:
        self.session = session
        self.repository = repository
        self.job_repository = job_repository
        self.storage = storage

    def enqueue_similarity_for_item(
        self,
        *,
        item: ClosetItem,
        actor_type: AuditActorType,
        actor_user_id: UUID | None,
        raise_on_duplicate: bool,
        trigger: str = "confirmation",
    ) -> bool:
        if not self._is_confirmed_item(item):
            raise build_error(INVALID_LIFECYCLE_TRANSITION)

        if self.job_repository.has_pending_or_running_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.SIMILARITY_RECOMPUTE,
        ):
            if raise_on_duplicate:
                raise build_error(SIMILARITY_RECOMPUTE_ALREADY_SCHEDULED)
            return False

        self.job_repository.enqueue_job(
            closet_item_id=item.id,
            job_kind=ProcessingRunType.SIMILARITY_RECOMPUTE,
            payload={"trigger": trigger},
        )
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            event_type="similarity_recompute_enqueued",
            payload={"trigger": trigger},
        )
        return True

    def enqueue_similarity_backfill(self) -> int:
        enqueued_count = 0
        for item in self.repository.list_all_confirmed_items():
            latest_run = self.repository.get_latest_processing_run(
                closet_item_id=item.id,
                run_type=ProcessingRunType.SIMILARITY_RECOMPUTE,
            )
            if latest_run is not None and latest_run.status in {
                ProcessingStatus.COMPLETED,
                ProcessingStatus.COMPLETED_WITH_ISSUES,
            }:
                continue
            if self.enqueue_similarity_for_item(
                item=item,
                actor_type=AuditActorType.SYSTEM,
                actor_user_id=None,
                raise_on_duplicate=False,
                trigger="backfill",
            ):
                enqueued_count += 1
        self.session.commit()
        return enqueued_count

    def list_similar_items(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        limit: int,
    ) -> SimilarityListSnapshot:
        return self._list_edges(
            item_id=item_id,
            user_id=user_id,
            limit=limit,
            mode="similar",
        )

    def list_duplicate_items(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        limit: int,
    ) -> SimilarityListSnapshot:
        return self._list_edges(
            item_id=item_id,
            user_id=user_id,
            limit=limit,
            mode="duplicates",
        )

    def dismiss_edge(
        self,
        *,
        edge_id: UUID,
        user_id: UUID,
    ) -> SimilarityEdgeSnapshot:
        edge = self.repository.get_similarity_edge_for_user(edge_id=edge_id, user_id=user_id)
        if edge is None:
            raise build_error(SIMILARITY_EDGE_NOT_FOUND)

        self.repository.delete_similarity_edges_for_pair(
            item_a_id=edge.item_a_id,
            item_b_id=edge.item_b_id,
            keep_edge_id=edge.id,
        )
        if edge.decision_status != SimilarityDecisionStatus.DISMISSED:
            edge.decision_status = SimilarityDecisionStatus.DISMISSED
            self.repository.create_audit_event(
                closet_item_id=edge.item_a_id,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                event_type="similarity_edge_dismissed",
                payload={"edge_id": str(edge.id), "other_item_id": str(edge.item_b_id)},
            )
            self.repository.create_audit_event(
                closet_item_id=edge.item_b_id,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                event_type="similarity_edge_dismissed",
                payload={"edge_id": str(edge.id), "other_item_id": str(edge.item_a_id)},
            )
        self.session.commit()
        self.session.refresh(edge)
        return self._build_edge_snapshot(edge=edge)

    def mark_edge_duplicate(
        self,
        *,
        edge_id: UUID,
        user_id: UUID,
    ) -> SimilarityEdgeSnapshot:
        edge = self.repository.get_similarity_edge_for_user(edge_id=edge_id, user_id=user_id)
        if edge is None:
            raise build_error(SIMILARITY_EDGE_NOT_FOUND)

        self.repository.delete_similarity_edges_for_pair(
            item_a_id=edge.item_a_id,
            item_b_id=edge.item_b_id,
            keep_edge_id=edge.id,
        )
        should_audit = not (
            edge.decision_status == SimilarityDecisionStatus.MARKED_DUPLICATE
            and edge.similarity_type == SimilarityType.DUPLICATE
        )
        edge.decision_status = SimilarityDecisionStatus.MARKED_DUPLICATE
        edge.similarity_type = SimilarityType.DUPLICATE
        if should_audit:
            self.repository.create_audit_event(
                closet_item_id=edge.item_a_id,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                event_type="similarity_edge_marked_duplicate",
                payload={"edge_id": str(edge.id), "other_item_id": str(edge.item_b_id)},
            )
            self.repository.create_audit_event(
                closet_item_id=edge.item_b_id,
                actor_type=AuditActorType.USER,
                actor_user_id=user_id,
                event_type="similarity_edge_marked_duplicate",
                payload={"edge_id": str(edge.id), "other_item_id": str(edge.item_a_id)},
            )
        self.session.commit()
        self.session.refresh(edge)
        return self._build_edge_snapshot(edge=edge)

    def handle_similarity_job(self, *, job: ClosetJob) -> None:
        item = self.repository.get_item(item_id=job.closet_item_id)
        if item is None:
            raise build_error(CLOSET_ITEM_NOT_FOUND)

        run = self.repository.create_processing_run(
            closet_item_id=item.id,
            run_type=ProcessingRunType.SIMILARITY_RECOMPUTE,
            status=ProcessingStatus.RUNNING,
            retry_count=self.repository.count_processing_runs(
                closet_item_id=item.id,
                run_type=ProcessingRunType.SIMILARITY_RECOMPUTE,
            ),
            started_at=utcnow(),
        )
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            event_type="similarity_recompute_started",
            payload={"processing_run_id": str(run.id)},
        )

        if not self._is_confirmed_item(item):
            self.repository.delete_similarity_edges_for_item(item_id=item.id)
            self._finalize_run(
                job=job,
                item=item,
                run=run,
                status=ProcessingStatus.COMPLETED_WITH_ISSUES,
                issues=["Item was no longer confirmed when similarity recompute ran."],
                compared_peer_count=0,
            )
            return

        anchor_row = self.repository.get_confirmed_item_with_projection_for_user(
            item_id=item.id,
            user_id=item.user_id,
        )
        if anchor_row is None:
            self._finalize_run(
                job=job,
                item=item,
                run=run,
                status=ProcessingStatus.COMPLETED_WITH_ISSUES,
                issues=["Confirmed item metadata projection was unavailable for similarity."],
                compared_peer_count=0,
            )
            return

        _, anchor_projection = anchor_row
        peer_rows = self.repository.list_confirmed_peer_items_with_projections(
            item_id=item.id,
            user_id=item.user_id,
        )
        all_item_ids = [item.id, *[peer.id for peer, _ in peer_rows]]
        images_by_item = self.repository.list_active_image_assets_for_items(
            closet_item_ids=all_item_ids,
            roles=[
                ClosetItemImageRole.THUMBNAIL,
                ClosetItemImageRole.PROCESSED,
                ClosetItemImageRole.ORIGINAL,
            ],
        )
        anchor_comparable = self._build_comparable_projection(
            projection=anchor_projection,
            images_by_role=images_by_item.get(item.id, {}),
            item_id=item.id,
        )
        issues = [anchor_comparable.issue] if anchor_comparable.issue is not None else []
        existing_edges_by_pair = self._group_edges_by_pair(
            self.repository.list_similarity_edges_for_item(item_id=item.id)
        )
        valid_peer_ids = {peer.id for peer, _ in peer_rows}

        for pair_key, edges in list(existing_edges_by_pair.items()):
            peer_item_id = pair_key[0] if pair_key[1] == item.id else pair_key[1]
            if peer_item_id not in valid_peer_ids:
                self.repository.delete_similarity_edges_for_pair(
                    item_a_id=pair_key[0],
                    item_b_id=pair_key[1],
                )
                existing_edges_by_pair.pop(pair_key, None)

        for peer_item, peer_projection in peer_rows:
            peer_comparable = self._build_comparable_projection(
                projection=peer_projection,
                images_by_role=images_by_item.get(peer_item.id, {}),
                item_id=peer_item.id,
            )
            if peer_comparable.issue is not None:
                issues.append(peer_comparable.issue)

            computation = compute_similarity(
                anchor_comparable.comparable_item,
                peer_comparable.comparable_item,
            )
            pair_key = canonicalize_similarity_pair(item.id, peer_item.id)
            existing_edges = existing_edges_by_pair.get(pair_key, [])
            preserved_edge = self._select_preserved_edge(existing_edges)

            if computation.similarity_type is None:
                if preserved_edge is None:
                    self.repository.delete_similarity_edges_for_pair(
                        item_a_id=pair_key[0],
                        item_b_id=pair_key[1],
                    )
                    continue
                preserved_edge = self.repository.save_similarity_edge(
                    edge=preserved_edge,
                    item_a_id=pair_key[0],
                    item_b_id=pair_key[1],
                    similarity_type=SimilarityType.DUPLICATE,
                    score=computation.score,
                    signals_json=computation.to_payload(),
                    decision_status=SimilarityDecisionStatus.MARKED_DUPLICATE,
                )
                self.repository.delete_similarity_edges_for_pair(
                    item_a_id=pair_key[0],
                    item_b_id=pair_key[1],
                    keep_edge_id=preserved_edge.id,
                )
                continue

            decision_status = SimilarityDecisionStatus.PENDING
            similarity_type = computation.similarity_type
            if preserved_edge is not None:
                if preserved_edge.decision_status == SimilarityDecisionStatus.DISMISSED:
                    decision_status = SimilarityDecisionStatus.DISMISSED
                elif preserved_edge.decision_status == SimilarityDecisionStatus.MARKED_DUPLICATE:
                    decision_status = SimilarityDecisionStatus.MARKED_DUPLICATE
                    similarity_type = SimilarityType.DUPLICATE

            saved_edge = self.repository.save_similarity_edge(
                edge=preserved_edge,
                item_a_id=pair_key[0],
                item_b_id=pair_key[1],
                similarity_type=similarity_type,
                score=computation.score,
                signals_json=computation.to_payload(),
                decision_status=decision_status,
            )
            self.repository.delete_similarity_edges_for_pair(
                item_a_id=pair_key[0],
                item_b_id=pair_key[1],
                keep_edge_id=saved_edge.id,
            )

        self._finalize_run(
            job=job,
            item=item,
            run=run,
            status=ProcessingStatus.COMPLETED_WITH_ISSUES if issues else ProcessingStatus.COMPLETED,
            issues=issues,
            compared_peer_count=len(peer_rows),
        )

    def _list_edges(
        self,
        *,
        item_id: UUID,
        user_id: UUID,
        limit: int,
        mode: str,
    ) -> SimilarityListSnapshot:
        anchor_row = self.repository.get_confirmed_item_with_projection_for_user(
            item_id=item_id,
            user_id=user_id,
        )
        if anchor_row is None:
            raise build_error(CLOSET_ITEM_NOT_FOUND)

        latest_run = self.repository.get_latest_processing_run(
            closet_item_id=item_id,
            run_type=ProcessingRunType.SIMILARITY_RECOMPUTE,
        )
        pending_or_running_job = self.job_repository.get_pending_or_running_job(
            closet_item_id=item_id,
            job_kind=ProcessingRunType.SIMILARITY_RECOMPUTE,
        )
        edges = self.repository.list_similarity_edges_for_item(item_id=item_id)
        visible_edges = self._filter_visible_edges(item_id=item_id, edges=edges, mode=mode)

        other_item_ids = [
            edge.item_b_id if edge.item_a_id == item_id else edge.item_a_id
            for edge in visible_edges
        ]
        item_map = self.repository.get_confirmed_items_with_projections_for_user(
            item_ids=other_item_ids,
            user_id=user_id,
        )
        visible_edges = [
            edge
            for edge in visible_edges
            if (edge.item_b_id if edge.item_a_id == item_id else edge.item_a_id) in item_map
        ]
        visible_edges.sort(
            key=lambda edge: (-edge.score, -edge.updated_at.timestamp(), str(edge.id))
        )
        visible_edges = visible_edges[:limit]

        preview_item_ids = [
            edge.item_b_id if edge.item_a_id == item_id else edge.item_a_id
            for edge in visible_edges
        ]
        images_by_item = self.repository.list_active_image_assets_for_items(
            closet_item_ids=preview_item_ids,
            roles=[
                ClosetItemImageRole.ORIGINAL,
                ClosetItemImageRole.PROCESSED,
                ClosetItemImageRole.THUMBNAIL,
            ],
        )
        items = [
            self._build_list_item_snapshot(
                edge=edge,
                other_item=item_map[
                    edge.item_b_id if edge.item_a_id == item_id else edge.item_a_id
                ][0],
                other_projection=item_map[
                    edge.item_b_id if edge.item_a_id == item_id else edge.item_a_id
                ][1],
                images_by_role=images_by_item.get(
                    edge.item_b_id if edge.item_a_id == item_id else edge.item_a_id,
                    {},
                ),
            )
            for edge in visible_edges
        ]
        return SimilarityListSnapshot(
            item_id=item_id,
            similarity_status=self._resolve_similarity_status(
                latest_run=latest_run,
                pending_or_running_job=pending_or_running_job,
            ),
            latest_run=latest_run,
            items=items,
        )

    def _build_list_item_snapshot(
        self,
        *,
        edge: ClosetItemSimilarityEdge,
        other_item: ClosetItem,
        other_projection: ClosetItemMetadataProjection,
        images_by_role: dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]],
    ) -> SimilarityListItemSnapshot:
        other_item_snapshot = build_browse_list_item_snapshot(
            item=other_item,
            projection=other_projection,
            images_by_role=images_by_role,
            storage=self.storage,
        )
        edge_snapshot = self._build_edge_snapshot(edge=edge)
        return SimilarityListItemSnapshot(
            edge_id=edge_snapshot.edge_id,
            label=edge_snapshot.label,
            similarity_type=edge_snapshot.similarity_type,
            decision_status=edge_snapshot.decision_status,
            score=edge_snapshot.score,
            signals=edge_snapshot.signals,
            other_item=other_item_snapshot,
        )

    def _build_edge_snapshot(self, *, edge: ClosetItemSimilarityEdge) -> SimilarityEdgeSnapshot:
        payload = edge.signals_json if isinstance(edge.signals_json, dict) else {}
        signal_payloads = payload.get("signals")
        parsed_signals = []
        if isinstance(signal_payloads, list):
            for signal_payload in signal_payloads:
                if not isinstance(signal_payload, dict):
                    continue
                parsed_signals.append(
                    SimilaritySignalSnapshot(
                        code=str(signal_payload.get("code", "")),
                        label=str(signal_payload.get("label", "")),
                        contribution=float(signal_payload.get("contribution", 0.0)),
                        metadata=signal_payload.get("metadata")
                        if isinstance(signal_payload.get("metadata"), dict)
                        else None,
                    )
                )
        return SimilarityEdgeSnapshot(
            edge_id=edge.id,
            item_a_id=edge.item_a_id,
            item_b_id=edge.item_b_id,
            label=self._similarity_label(edge.similarity_type),
            similarity_type=edge.similarity_type.value,
            decision_status=edge.decision_status.value,
            score=edge.score,
            signals=parsed_signals,
        )

    def _build_preview_image(
        self,
        image_record: tuple[ClosetItemImage, MediaAsset] | None,
        *,
        primary_image_id: UUID | None = None,
    ) -> ProcessingSnapshotImage | None:
        if image_record is None:
            return None
        item_image, asset = image_record
        presigned_download = self.storage.generate_presigned_download(
            bucket=asset.bucket,
            key=asset.key,
            expires_in_seconds=settings.closet_media_download_ttl_seconds,
        )
        return ProcessingSnapshotImage(
            asset_id=asset.id,
            image_id=item_image.id,
            role=item_image.role.value,
            position=(
                item_image.position if item_image.role == ClosetItemImageRole.ORIGINAL else None
            ),
            is_primary=primary_image_id == item_image.id,
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            url=presigned_download.url,
            expires_at=presigned_download.expires_at,
        )

    def _build_comparable_projection(
        self,
        *,
        projection: ClosetItemMetadataProjection,
        images_by_role: dict[ClosetItemImageRole, tuple[ClosetItemImage, MediaAsset]],
        item_id: UUID,
    ) -> _ComparableProjection:
        selected_image = None
        for role in (
            ClosetItemImageRole.THUMBNAIL,
            ClosetItemImageRole.PROCESSED,
            ClosetItemImageRole.ORIGINAL,
        ):
            selected_image = images_by_role.get(role)
            if selected_image is not None:
                break

        image_bytes: bytes | None = None
        image_role: str | None = None
        issue: str | None = None
        if selected_image is not None:
            item_image, asset = selected_image
            image_role = item_image.role.value
            try:
                image_bytes = self.storage.get_object_bytes(bucket=asset.bucket, key=asset.key)
            except FileNotFoundError:
                issue = f"Comparison image was unavailable for item {item_id}."
        else:
            issue = f"No comparison image was available for item {item_id}."

        return _ComparableProjection(
            comparable_item=ComparableItem(
                title=projection.title,
                category=projection.category,
                subcategory=projection.subcategory,
                primary_color=projection.primary_color,
                secondary_colors=projection.secondary_colors,
                material=projection.material,
                pattern=projection.pattern,
                brand=projection.brand,
                image_bytes=image_bytes,
                image_role=image_role,
            ),
            issue=issue,
        )

    def _filter_visible_edges(
        self,
        *,
        item_id: UUID,
        edges: list[ClosetItemSimilarityEdge],
        mode: str,
    ) -> list[ClosetItemSimilarityEdge]:
        visible_edges: list[ClosetItemSimilarityEdge] = []
        for edge in edges:
            if edge.item_a_id != item_id and edge.item_b_id != item_id:
                continue
            if mode == "similar":
                if edge.decision_status != SimilarityDecisionStatus.PENDING:
                    continue
                if edge.similarity_type != SimilarityType.SIMILAR:
                    continue
            else:
                if edge.decision_status == SimilarityDecisionStatus.DISMISSED:
                    continue
                if (
                    edge.decision_status == SimilarityDecisionStatus.PENDING
                    and edge.similarity_type == SimilarityType.DUPLICATE_CANDIDATE
                ):
                    visible_edges.append(edge)
                    continue
                if (
                    edge.decision_status == SimilarityDecisionStatus.MARKED_DUPLICATE
                    and edge.similarity_type == SimilarityType.DUPLICATE
                ):
                    visible_edges.append(edge)
                continue
            visible_edges.append(edge)
        return visible_edges

    def _group_edges_by_pair(
        self,
        edges: list[ClosetItemSimilarityEdge],
    ) -> dict[tuple[UUID, UUID], list[ClosetItemSimilarityEdge]]:
        grouped: dict[tuple[UUID, UUID], list[ClosetItemSimilarityEdge]] = {}
        for edge in edges:
            key = canonicalize_similarity_pair(edge.item_a_id, edge.item_b_id)
            grouped.setdefault(key, []).append(edge)
        return grouped

    def _select_preserved_edge(
        self,
        edges: list[ClosetItemSimilarityEdge],
    ) -> ClosetItemSimilarityEdge | None:
        if not edges:
            return None
        for edge in edges:
            if edge.decision_status == SimilarityDecisionStatus.MARKED_DUPLICATE:
                return edge
        for edge in edges:
            if edge.decision_status == SimilarityDecisionStatus.DISMISSED:
                return edge
        return edges[0]

    def _resolve_similarity_status(
        self,
        *,
        latest_run: ProcessingRun | None,
        pending_or_running_job: ClosetJob | None,
    ) -> str:
        if pending_or_running_job is not None:
            if pending_or_running_job.status == ClosetJobStatus.RUNNING:
                return "running"
            return "pending"
        if latest_run is None:
            return "not_requested"
        return latest_run.status.value

    def _finalize_run(
        self,
        *,
        job: ClosetJob,
        item: ClosetItem,
        run: ProcessingRun,
        status: ProcessingStatus,
        issues: list[str],
        compared_peer_count: int,
    ) -> None:
        unique_issues: list[str] = []
        for issue in issues:
            if issue and issue not in unique_issues:
                unique_issues.append(issue)

        run.status = status
        run.completed_at = utcnow()
        run.failure_code = "similarity_recompute_issues" if unique_issues else None
        run.failure_payload = {"issues": unique_issues} if unique_issues else None
        payload = job.payload.copy() if isinstance(job.payload, dict) else {}
        payload["result_status"] = status.value
        payload["processing_run_id"] = str(run.id)
        payload["issue_count"] = len(unique_issues)
        payload["compared_peer_count"] = compared_peer_count
        job.payload = payload
        self.repository.create_audit_event(
            closet_item_id=item.id,
            actor_type=AuditActorType.WORKER,
            actor_user_id=None,
            event_type=(
                "similarity_recompute_completed_with_issues"
                if unique_issues
                else "similarity_recompute_completed"
            ),
            payload={
                "processing_run_id": str(run.id),
                "issue_count": len(unique_issues),
                "compared_peer_count": compared_peer_count,
            },
        )
        self.session.flush()

    def _is_confirmed_item(self, item: ClosetItem) -> bool:
        return (
            item.lifecycle_status == LifecycleStatus.CONFIRMED
            and item.review_status == ReviewStatus.CONFIRMED
            and item.confirmed_at is not None
        )

    def _similarity_label(self, similarity_type: SimilarityType) -> str:
        if similarity_type == SimilarityType.DUPLICATE:
            return "duplicate"
        if similarity_type == SimilarityType.DUPLICATE_CANDIDATE:
            return "possible_duplicate"
        return "similar_item"
