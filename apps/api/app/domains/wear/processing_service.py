from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ObjectStorageClient
from app.domains.closet.models import ApplicabilityState, MediaAssetSourceKind
from app.domains.closet.normalization import normalize_field_value
from app.domains.closet.taxonomy import CATEGORY_SUBCATEGORIES, is_valid_category_subcategory_pair
from app.domains.wear.detection import (
    OUTFIT_DETECTION_TASK_TYPE,
    DetectedOutfitItem,
    OutfitDetectionProvider,
)
from app.domains.wear.matching_service import WearDetectionInput, WearMatchingService
from app.domains.wear.models import (
    WearDetectedItemStatus,
    WearLogStatus,
    WearProcessingRunType,
    WearProcessingStatus,
    WearProviderResultStatus,
)
from app.domains.wear.repository import WearJobRepository, WearRepository
from app.domains.wear.service import WearLogDetailSnapshot, WearService

_SUBCATEGORY_TO_CATEGORY = {
    subcategory: category
    for category, subcategories in CATEGORY_SUBCATEGORIES.items()
    for subcategory in subcategories
}

_ROLE_SYNONYMS = {
    "glasses": "eyewear",
    "eyeglasses": "eyewear",
    "sunglasses": "eyewear",
    "shoe": "footwear",
    "shoes": "footwear",
    "jacket": "outerwear",
    "coat": "outerwear",
    "blazer": "outerwear",
    "vest": "outerwear",
    "pants": "bottom",
    "trousers": "bottom",
    "jeans": "bottom",
    "skirt": "bottom",
    "shorts": "bottom",
    "bag": "bag",
    "handbag": "bag",
    "purse": "bag",
    "necklace": "jewelry",
    "bracelet": "jewelry",
    "ring": "jewelry",
    "watch": "jewelry",
    "earrings": "jewelry",
    "earring": "jewelry",
}

_SUPPORTED_WEAR_ROLES = {
    "top",
    "bottom",
    "footwear",
    "outerwear",
    "dress",
    "full_body",
    "bag",
    "accessory",
    "jewelry",
    "hat",
    "scarf",
    "eyewear",
}


@dataclass(frozen=True)
class NormalizedWearDetection:
    role: str | None
    category: str | None
    subcategory: str | None
    colors: list[str]
    material: str | None
    pattern: str | None
    fit_tags: list[str]
    silhouette: str | None
    attributes: list[str]
    confidence: float | None
    bbox: dict[str, float] | None


class WearProcessingError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class WearProcessingService:
    def __init__(
        self,
        *,
        session: Session,
        repository: WearRepository,
        job_repository: WearJobRepository,
        storage: ObjectStorageClient,
        detection_provider: OutfitDetectionProvider,
        matching_service: WearMatchingService,
    ) -> None:
        self.session = session
        self.repository = repository
        self.job_repository = job_repository
        self.storage = storage
        self.detection_provider = detection_provider
        self.matching_service = matching_service

    def reprocess_wear_log(
        self,
        *,
        wear_log_id: UUID,
        user_id: UUID,
    ) -> tuple[WearLogDetailSnapshot, int]:
        wear_log = self.repository.get_wear_log_for_user(
            wear_log_id=wear_log_id,
            user_id=user_id,
        )
        if wear_log is None:
            raise WearProcessingError(404, "Wear log not found.")
        if wear_log.archived_at is not None:
            raise WearProcessingError(409, "Archived wear events cannot be reprocessed.")
        if wear_log.primary_photo_id is None:
            raise WearProcessingError(409, "Wear event does not have a primary photo to analyze.")
        if wear_log.status == WearLogStatus.CONFIRMED:
            raise WearProcessingError(
                409,
                "Confirmed wear events are immutable for detection reprocessing in v1.",
            )

        wear_log.status = WearLogStatus.PROCESSING
        wear_log.failure_code = None
        wear_log.failure_summary = None

        if not self.job_repository.has_pending_or_running_job(
            wear_log_id=wear_log.id,
            job_kind=WearProcessingRunType.PHOTO_ANALYSIS,
        ):
            self.job_repository.enqueue_job(
                wear_log_id=wear_log.id,
                job_kind=WearProcessingRunType.PHOTO_ANALYSIS,
            )

        self.session.commit()

        detail = WearService(
            session=self.session,
            repository=self.repository,
            storage=self.storage,
        ).get_wear_log_detail(
            wear_log_id=wear_log.id,
            user_id=user_id,
        )

        return detail, 202

    def handle_photo_analysis_job(self, *, wear_log_id: UUID) -> None:
        wear_log = self.repository.get_wear_log_for_user(
            wear_log_id=wear_log_id,
            user_id=self._get_owner_id(wear_log_id),
        )
        if wear_log is None:
            raise WearProcessingError(404, "Wear log not found.")
        if wear_log.primary_photo_id is None:
            raise WearProcessingError(409, "Wear event does not have a primary photo to analyze.")

        photo = self.repository.get_wear_event_photo(photo_id=wear_log.primary_photo_id)
        if photo is None:
            raise WearProcessingError(409, "Wear event primary photo could not be found.")

        assets_by_id = self.repository.get_media_assets_by_ids(asset_ids=[photo.asset_id])
        asset = assets_by_id.get(photo.asset_id)
        if asset is None:
            raise WearProcessingError(409, "Wear event photo asset could not be found.")

        image_bytes = self.storage.get_object_bytes(bucket=asset.bucket, key=asset.key)
        now = utcnow()

        run = self.repository.create_processing_run(
            wear_log_id=wear_log.id,
            run_type=WearProcessingRunType.PHOTO_ANALYSIS,
            status=WearProcessingStatus.RUNNING,
            started_at=now,
        )

        try:
            result = self.detection_provider.detect_outfit_items(
                image_bytes=image_bytes,
                filename=self._build_detection_filename(
                    wear_log_id=wear_log.id,
                    mime_type=asset.mime_type,
                ),
                mime_type=asset.mime_type,
            )

            self.repository.create_provider_result(
                wear_log_id=wear_log.id,
                processing_run_id=run.id,
                provider_name=result.provider_name,
                provider_model=result.provider_model,
                provider_version=result.provider_version,
                task_type=OUTFIT_DETECTION_TASK_TYPE,
                status=result.status,
                raw_payload=result.sanitized_payload,
            )

            self.repository.clear_detected_items_for_log(wear_log_id=wear_log.id)

            if result.status == WearProviderResultStatus.FAILED:
                wear_log.status = WearLogStatus.FAILED
                wear_log.failure_code = str(
                    result.sanitized_payload.get("reason_code") or "detection_failed"
                )
                wear_log.failure_summary = str(
                    result.sanitized_payload.get("message") or "Wear-event detection failed."
                )
                run.status = WearProcessingStatus.FAILED
                run.completed_at = now
                run.failure_code = wear_log.failure_code
                run.failure_payload = result.sanitized_payload
                self.session.flush()
                return

            normalized_detections = self._normalize_and_dedupe_detections(result.detections)

            if not normalized_detections:
                wear_log.status = WearLogStatus.FAILED
                wear_log.failure_code = "no_detected_items"
                wear_log.failure_summary = (
                    "We could not confidently detect outfit items from this photo."
                )
                run.status = WearProcessingStatus.FAILED
                run.completed_at = now
                run.failure_code = wear_log.failure_code
                run.failure_payload = {
                    "provider_detections_count": len(result.detections),
                    "normalized_detections_count": 0,
                    "message": wear_log.failure_summary,
                }
                self.session.flush()
                return

            surfaced_count = 0
            matched_count = 0

            for sort_index, detection in enumerate(normalized_detections):
                detection_input = WearDetectionInput(
                    role=detection.role,
                    category=detection.category,
                    subcategory=detection.subcategory,
                    colors=list(detection.colors),
                    material=detection.material,
                    pattern=detection.pattern,
                    fit_tags=list(detection.fit_tags),
                    silhouette=detection.silhouette,
                    attributes=list(detection.attributes),
                    confidence=detection.confidence,
                )

                ranked_candidates = self.matching_service.rank_candidates_for_detection(
                    user_id=wear_log.user_id,
                    detection=detection_input,
                    limit=3,
                )

                crop_asset_id = self._create_detection_crop_asset(
                    user_id=wear_log.user_id,
                    wear_log_id=wear_log.id,
                    source_bytes=image_bytes,
                    source_mime_type=asset.mime_type,
                    bbox=detection.bbox,
                )

                detected_item = self.repository.create_detected_item(
                    wear_log_id=wear_log.id,
                    processing_run_id=run.id,
                    sort_index=sort_index,
                    predicted_role=self._coerce_detected_role(detection.role),
                    predicted_category=detection.category,
                    predicted_subcategory=detection.subcategory,
                    predicted_colors_json=list(detection.colors),
                    predicted_material=detection.material,
                    predicted_pattern=detection.pattern,
                    predicted_fit_tags_json=list(detection.fit_tags),
                    predicted_silhouette=detection.silhouette,
                    predicted_attributes_json=list(detection.attributes),
                    confidence=detection.confidence,
                    bbox_json=detection.bbox,
                    crop_asset_id=crop_asset_id,
                    status=WearDetectedItemStatus.DETECTED,
                )

                for candidate in ranked_candidates:
                    self.repository.create_match_candidate(
                        detected_item_id=detected_item.id,
                        closet_item_id=candidate.closet_item_id,
                        rank=candidate.rank,
                        score=candidate.score,
                        signals_json=candidate.signals_json,
                    )

                surfaced_count += 1
                if ranked_candidates:
                    matched_count += 1

            wear_log.status = WearLogStatus.NEEDS_REVIEW
            wear_log.failure_code = None
            wear_log.failure_summary = None
            run.status = WearProcessingStatus.COMPLETED
            run.completed_at = now
            run.failure_code = None
            run.failure_payload = {
                "provider_detections_count": len(result.detections),
                "normalized_detections_count": len(normalized_detections),
                "surfaced_count": surfaced_count,
                "matched_count": matched_count,
                "unmatched_count": surfaced_count - matched_count,
            }
            self.session.flush()

        except Exception as exc:
            wear_log.status = WearLogStatus.FAILED
            wear_log.failure_code = "processing_failed"
            wear_log.failure_summary = str(exc)
            run.status = WearProcessingStatus.FAILED
            run.completed_at = now
            run.failure_code = "processing_failed"
            run.failure_payload = {"message": str(exc)}
            self.session.flush()
            raise

    def _normalize_and_dedupe_detections(
        self,
        detections: list[DetectedOutfitItem],
    ) -> list[NormalizedWearDetection]:
        normalized: list[NormalizedWearDetection] = []
        seen: set[tuple[object, ...]] = set()

        for raw_detection in detections:
            item = self._normalize_detection(raw_detection)
            if item is None:
                continue

            dedupe_key = (
                item.role,
                item.category,
                item.subcategory,
                tuple(item.colors),
                item.material,
                item.pattern,
                tuple(item.fit_tags),
                item.silhouette,
                tuple(item.attributes),
                _rounded_bbox_key(item.bbox),
            )
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            normalized.append(item)

        return normalized

    def _normalize_detection(
        self,
        detection: DetectedOutfitItem,
    ) -> NormalizedWearDetection | None:
        category = _normalize_scalar_field("category", detection.category)
        subcategory = _normalize_scalar_field("subcategory", detection.subcategory)

        if subcategory is not None:
            mapped_category = _SUBCATEGORY_TO_CATEGORY.get(subcategory)
            if mapped_category is not None:
                category = mapped_category

        role = _normalize_role(
            detection.role,
            category=category,
            subcategory=subcategory,
        )

        if category is None:
            category = _infer_category_from_role(role)

        if role is None:
            role = _infer_role_from_category_subcategory(
                category=category,
                subcategory=subcategory,
            )

        if category is not None and subcategory is not None:
            if not is_valid_category_subcategory_pair(
                category=category,
                subcategory=subcategory,
            ):
                subcategory = None

        colors = _normalize_list_field("colors", detection.colors)
        material = _normalize_scalar_field("material", detection.material)
        pattern = _normalize_scalar_field("pattern", detection.pattern)
        fit_tags = _normalize_list_field("fit_tags", detection.fit_tags)
        silhouette = _normalize_scalar_field("silhouette", detection.silhouette)
        attributes = _normalize_list_field("attributes", detection.attributes)
        confidence = _clamp_confidence(detection.confidence)
        bbox = detection.bbox if isinstance(detection.bbox, dict) else None

        if (
            role is None
            and category is None
            and subcategory is None
            and not colors
            and material is None
            and pattern is None
            and not fit_tags
            and silhouette is None
            and not attributes
        ):
            return None

        return NormalizedWearDetection(
            role=role,
            category=category,
            subcategory=subcategory,
            colors=colors,
            material=material,
            pattern=pattern,
            fit_tags=fit_tags,
            silhouette=silhouette,
            attributes=attributes,
            confidence=confidence,
            bbox=bbox,
        )

    def _build_detection_filename(self, *, wear_log_id: UUID, mime_type: str) -> str:
        extension = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }.get(mime_type, "bin")
        return f"{wear_log_id}.{extension}"

    def _create_detection_crop_asset(
        self,
        *,
        user_id: UUID,
        wear_log_id: UUID,
        source_bytes: bytes,
        source_mime_type: str,
        bbox: dict[str, float] | None,
    ) -> UUID | None:
        if bbox is None:
            return None

        crop_bytes, crop_mime_type, width, height = crop_image(
            image_bytes=source_bytes,
            mime_type=source_mime_type,
            bbox=bbox,
        )
        if crop_bytes is None:
            return None

        asset_id = uuid4()
        key = build_detection_crop_key(
            user_id=user_id,
            wear_log_id=wear_log_id,
            asset_id=asset_id,
        )

        self.storage.put_object_bytes(
            bucket=settings.minio_bucket,
            key=key,
            content=crop_bytes,
            content_type=crop_mime_type,
        )

        self.repository.create_media_asset(
            asset_id=asset_id,
            user_id=user_id,
            bucket=settings.minio_bucket,
            key=key,
            mime_type=crop_mime_type,
            file_size=len(crop_bytes),
            checksum=hash_bytes(crop_bytes),
            width=width,
            height=height,
            source_kind=MediaAssetSourceKind.DERIVED,
            is_private=True,
        )

        return asset_id

    def _get_owner_id(self, wear_log_id: UUID) -> UUID:
        statement = select_owner_id(self.session, wear_log_id=wear_log_id)
        if statement is None:
            raise WearProcessingError(404, "Wear log not found.")
        return statement

    def _coerce_detected_role(self, value: str | None):
        from app.domains.wear.models import WearItemRole

        if value is None:
            return None

        normalized = value.strip().lower()
        if normalized in {"top"}:
            return WearItemRole.TOP
        if normalized in {"bottom"}:
            return WearItemRole.BOTTOM
        if normalized in {"dress", "full_body"}:
            return WearItemRole.DRESS
        if normalized in {"outerwear"}:
            return WearItemRole.OUTERWEAR
        if normalized in {"footwear"}:
            return WearItemRole.SHOES
        if normalized in {"bag"}:
            return WearItemRole.BAG
        if normalized in {"accessory", "jewelry", "hat", "scarf", "eyewear"}:
            return WearItemRole.ACCESSORY

        try:
            return WearItemRole(normalized)
        except ValueError:
            return WearItemRole.OTHER


def select_owner_id(session: Session, *, wear_log_id: UUID) -> UUID | None:
    from sqlalchemy import select

    from app.domains.wear.models import WearLog

    statement = select(WearLog.user_id).where(WearLog.id == wear_log_id)
    return session.execute(statement).scalar_one_or_none()


def build_detection_crop_key(*, user_id: UUID, wear_log_id: UUID, asset_id: UUID) -> str:
    return f"wear-events/detections/{user_id}/{wear_log_id}/{asset_id}"


def hash_bytes(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)


def crop_image(
    *,
    image_bytes: bytes,
    mime_type: str,
    bbox: dict[str, float],
) -> tuple[bytes | None, str, int | None, int | None]:
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError):
        return None, mime_type, None, None

    left = float(bbox.get("left", bbox.get("x", 0.0)))
    top = float(bbox.get("top", bbox.get("y", 0.0)))
    width = bbox.get("width", bbox.get("w"))
    height = bbox.get("height", bbox.get("h"))

    if width is None and "right" in bbox:
        width = float(bbox["right"]) - left
    if height is None and "bottom" in bbox:
        height = float(bbox["bottom"]) - top
    if width is None or height is None:
        return None, mime_type, None, None

    left_px = max(0, min(image.width - 1, int(left * image.width)))
    top_px = max(0, min(image.height - 1, int(top * image.height)))
    right_px = max(left_px + 1, min(image.width, int((left + float(width)) * image.width)))
    bottom_px = max(top_px + 1, min(image.height, int((top + float(height)) * image.height)))

    if right_px <= left_px or bottom_px <= top_px:
        return None, mime_type, None, None

    cropped = image.crop((left_px, top_px, right_px, bottom_px))
    output = BytesIO()

    format_name = (
        "JPEG" if mime_type == "image/jpeg"
        else "PNG" if mime_type == "image/png"
        else "WEBP"
    )
    save_kwargs = {"quality": 90} if format_name in {"JPEG", "WEBP"} else {}

    cropped.save(output, format=format_name, **save_kwargs)
    return output.getvalue(), mime_type, cropped.width, cropped.height


def _normalize_scalar_field(field_name: str, raw_value: Any) -> str | None:
    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=raw_value,
        applicability_state=ApplicabilityState.VALUE,
        confidence=None,
    )
    value = normalized.canonical_value
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _normalize_list_field(field_name: str, raw_value: Any) -> list[str]:
    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=raw_value,
        applicability_state=ApplicabilityState.VALUE,
        confidence=None,
    )
    value = normalized.canonical_value
    if not isinstance(value, list):
        return []

    deduped: list[str] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            continue
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)

    return deduped


def _normalize_role(
    value: str | None,
    *,
    category: str | None,
    subcategory: str | None,
) -> str | None:
    if value:
        lowered = value.strip().lower()
        lowered = _ROLE_SYNONYMS.get(lowered, lowered)
        if lowered in _SUPPORTED_WEAR_ROLES:
            return lowered

    return _infer_role_from_category_subcategory(
        category=category,
        subcategory=subcategory,
    )


def _infer_role_from_category_subcategory(
    *,
    category: str | None,
    subcategory: str | None,
) -> str | None:
    text = " ".join(part for part in [category, subcategory] if part).strip().lower()

    if category == "outerwear":
        return "outerwear"
    if category == "tops":
        return "top"
    if category == "bottoms":
        return "bottom"
    if category == "shoes":
        return "footwear"
    if category == "bags":
        return "bag"
    if category == "jewelry":
        return "jewelry"
    if category == "dresses":
        return "dress"
    if category == "one_piece":
        return "full_body"
    if category == "accessories":
        if "hat" in text:
            return "hat"
        if "scarf" in text:
            return "scarf"
        if "sunglasses" in text:
            return "eyewear"
        return "accessory"

    if subcategory in {"cardigan", "blazer", "jacket", "coat", "trench coat", "vest"}:
        return "outerwear"
    if subcategory in {
        "t-shirt",
        "shirt",
        "blouse",
        "tank top",
        "camisole",
        "polo",
        "sweater",
        "sweatshirt",
        "hoodie",
        "bodysuit",
    }:
        return "top"
    if subcategory in {"jeans", "trousers", "shorts", "skirt", "leggings", "joggers"}:
        return "bottom"
    if subcategory in {"sneakers", "boots", "heels", "flats", "loafers", "sandals", "mules"}:
        return "footwear"
    if subcategory in {"tote", "shoulder bag", "crossbody", "backpack", "clutch"}:
        return "bag"
    if subcategory in {"necklace", "earrings", "bracelet", "ring", "watch"}:
        return "jewelry"
    if subcategory in {
        "mini dress",
        "midi dress",
        "maxi dress",
        "slip dress",
        "shirt dress",
        "sweater dress",
    }:
        return "dress"
    if subcategory in {"jumpsuit", "romper"}:
        return "full_body"
    if subcategory == "hat":
        return "hat"
    if subcategory == "scarf":
        return "scarf"
    if subcategory == "sunglasses":
        return "eyewear"

    return None


def _infer_category_from_role(role: str | None) -> str | None:
    if role == "top":
        return "tops"
    if role == "bottom":
        return "bottoms"
    if role == "outerwear":
        return "outerwear"
    if role == "footwear":
        return "shoes"
    if role == "bag":
        return "bags"
    if role == "jewelry":
        return "jewelry"
    if role == "dress":
        return "dresses"
    if role == "full_body":
        return "one_piece"
    if role in {"hat", "scarf", "eyewear", "accessory"}:
        return "accessories"
    return None


def _clamp_confidence(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, numeric))


def _rounded_bbox_key(
    bbox: dict[str, float] | None,
) -> tuple[float, float, float, float] | None:
    if not isinstance(bbox, dict):
        return None
    try:
        return (
            round(float(bbox.get("x", 0.0)), 3),
            round(float(bbox.get("y", 0.0)), 3),
            round(float(bbox.get("width", 0.0)), 3),
            round(float(bbox.get("height", 0.0)), 3),
        )
    except (TypeError, ValueError):
        return None
