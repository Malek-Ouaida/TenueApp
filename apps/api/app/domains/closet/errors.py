from dataclasses import dataclass

CLOSET_ITEM_NOT_FOUND = "closet_item_not_found"
INVALID_LIFECYCLE_TRANSITION = "invalid_lifecycle_transition"
MISSING_PRIMARY_IMAGE = "missing_primary_image"
MISSING_REQUIRED_CONFIRMATION_FIELDS = "missing_required_confirmation_fields"
UNSUPPORTED_TAXONOMY_VERSION = "unsupported_taxonomy_version"
INVALID_FIELD_NAME = "invalid_field_name"
JOB_NOT_CLAIMABLE = "job_not_claimable"
JOB_RETRY_EXHAUSTED = "job_retry_exhausted"
UNSUPPORTED_JOB_HANDLER = "unsupported_job_handler"
UPLOAD_INTENT_NOT_FOUND = "upload_intent_not_found"
UPLOAD_INTENT_EXPIRED = "upload_intent_expired"
UPLOAD_ALREADY_FINALIZED = "upload_already_finalized"
UPLOAD_NOT_PRESENT = "upload_not_present"
UPLOAD_CHECKSUM_MISMATCH = "upload_checksum_mismatch"
UPLOAD_VALIDATION_FAILED = "upload_validation_failed"
UNSUPPORTED_UPLOAD_MIME_TYPE = "unsupported_upload_mime_type"
UPLOAD_TOO_LARGE = "upload_too_large"
UPLOAD_DIMENSIONS_EXCEEDED = "upload_dimensions_exceeded"
IDEMPOTENCY_CONFLICT = "idempotency_conflict"
PROCESSING_ALREADY_SCHEDULED = "processing_already_scheduled"
METADATA_EXTRACTION_ALREADY_SCHEDULED = "metadata_extraction_already_scheduled"
METADATA_EXTRACTION_NOT_READY = "metadata_extraction_not_ready"
METADATA_EXTRACTION_SOURCE_MISSING = "metadata_extraction_source_missing"
METADATA_NORMALIZATION_ALREADY_SCHEDULED = "metadata_normalization_already_scheduled"
METADATA_NORMALIZATION_NOT_READY = "metadata_normalization_not_ready"
METADATA_NORMALIZATION_CANDIDATE_SET_MISSING = "metadata_normalization_candidate_set_missing"
STALE_REVIEW_VERSION = "stale_review_version"
INVALID_REVIEW_MUTATION = "invalid_review_mutation"
REVIEW_NOT_AVAILABLE = "review_not_available"
RETRY_NOT_AVAILABLE = "retry_not_available"
REVIEW_SUGGESTION_MISSING = "review_suggestion_missing"


@dataclass(frozen=True)
class ClosetErrorDefinition:
    code: str
    status_code: int
    detail: str


ERROR_DEFINITIONS = {
    CLOSET_ITEM_NOT_FOUND: ClosetErrorDefinition(
        code=CLOSET_ITEM_NOT_FOUND,
        status_code=404,
        detail="Closet item not found.",
    ),
    INVALID_LIFECYCLE_TRANSITION: ClosetErrorDefinition(
        code=INVALID_LIFECYCLE_TRANSITION,
        status_code=409,
        detail="Invalid closet lifecycle transition.",
    ),
    MISSING_PRIMARY_IMAGE: ClosetErrorDefinition(
        code=MISSING_PRIMARY_IMAGE,
        status_code=422,
        detail="A primary image is required for this action.",
    ),
    MISSING_REQUIRED_CONFIRMATION_FIELDS: ClosetErrorDefinition(
        code=MISSING_REQUIRED_CONFIRMATION_FIELDS,
        status_code=422,
        detail="Category and subcategory are required before confirmation.",
    ),
    UNSUPPORTED_TAXONOMY_VERSION: ClosetErrorDefinition(
        code=UNSUPPORTED_TAXONOMY_VERSION,
        status_code=422,
        detail="Unsupported taxonomy version.",
    ),
    INVALID_FIELD_NAME: ClosetErrorDefinition(
        code=INVALID_FIELD_NAME,
        status_code=422,
        detail="Invalid closet metadata field name.",
    ),
    JOB_NOT_CLAIMABLE: ClosetErrorDefinition(
        code=JOB_NOT_CLAIMABLE,
        status_code=409,
        detail="The requested closet job cannot be claimed.",
    ),
    JOB_RETRY_EXHAUSTED: ClosetErrorDefinition(
        code=JOB_RETRY_EXHAUSTED,
        status_code=409,
        detail="The closet job has exhausted its retry budget.",
    ),
    UNSUPPORTED_JOB_HANDLER: ClosetErrorDefinition(
        code=UNSUPPORTED_JOB_HANDLER,
        status_code=501,
        detail="No worker handler is defined for this closet job kind.",
    ),
    UPLOAD_INTENT_NOT_FOUND: ClosetErrorDefinition(
        code=UPLOAD_INTENT_NOT_FOUND,
        status_code=404,
        detail="Upload intent not found.",
    ),
    UPLOAD_INTENT_EXPIRED: ClosetErrorDefinition(
        code=UPLOAD_INTENT_EXPIRED,
        status_code=409,
        detail="The upload intent has expired.",
    ),
    UPLOAD_ALREADY_FINALIZED: ClosetErrorDefinition(
        code=UPLOAD_ALREADY_FINALIZED,
        status_code=409,
        detail="The upload intent has already been finalized.",
    ),
    UPLOAD_NOT_PRESENT: ClosetErrorDefinition(
        code=UPLOAD_NOT_PRESENT,
        status_code=409,
        detail="The uploaded object is not present in storage.",
    ),
    UPLOAD_CHECKSUM_MISMATCH: ClosetErrorDefinition(
        code=UPLOAD_CHECKSUM_MISMATCH,
        status_code=409,
        detail="The uploaded checksum did not match the declared checksum.",
    ),
    UPLOAD_VALIDATION_FAILED: ClosetErrorDefinition(
        code=UPLOAD_VALIDATION_FAILED,
        status_code=422,
        detail="The uploaded object failed validation.",
    ),
    UNSUPPORTED_UPLOAD_MIME_TYPE: ClosetErrorDefinition(
        code=UNSUPPORTED_UPLOAD_MIME_TYPE,
        status_code=422,
        detail="The uploaded MIME type is not supported.",
    ),
    UPLOAD_TOO_LARGE: ClosetErrorDefinition(
        code=UPLOAD_TOO_LARGE,
        status_code=422,
        detail="The uploaded file exceeds the allowed size limit.",
    ),
    UPLOAD_DIMENSIONS_EXCEEDED: ClosetErrorDefinition(
        code=UPLOAD_DIMENSIONS_EXCEEDED,
        status_code=422,
        detail="The uploaded image exceeds the allowed dimensions.",
    ),
    IDEMPOTENCY_CONFLICT: ClosetErrorDefinition(
        code=IDEMPOTENCY_CONFLICT,
        status_code=409,
        detail="The idempotency key was reused with a different request payload.",
    ),
    PROCESSING_ALREADY_SCHEDULED: ClosetErrorDefinition(
        code=PROCESSING_ALREADY_SCHEDULED,
        status_code=409,
        detail="Image processing is already scheduled for this closet item.",
    ),
    METADATA_EXTRACTION_ALREADY_SCHEDULED: ClosetErrorDefinition(
        code=METADATA_EXTRACTION_ALREADY_SCHEDULED,
        status_code=409,
        detail="Metadata extraction is already scheduled for this closet item.",
    ),
    METADATA_EXTRACTION_NOT_READY: ClosetErrorDefinition(
        code=METADATA_EXTRACTION_NOT_READY,
        status_code=409,
        detail="This closet item is not ready for metadata extraction yet.",
    ),
    METADATA_EXTRACTION_SOURCE_MISSING: ClosetErrorDefinition(
        code=METADATA_EXTRACTION_SOURCE_MISSING,
        status_code=422,
        detail="No usable image source is available for metadata extraction.",
    ),
    METADATA_NORMALIZATION_ALREADY_SCHEDULED: ClosetErrorDefinition(
        code=METADATA_NORMALIZATION_ALREADY_SCHEDULED,
        status_code=409,
        detail="Metadata normalization is already scheduled for this closet item.",
    ),
    METADATA_NORMALIZATION_NOT_READY: ClosetErrorDefinition(
        code=METADATA_NORMALIZATION_NOT_READY,
        status_code=409,
        detail="This closet item is not ready for metadata normalization yet.",
    ),
    METADATA_NORMALIZATION_CANDIDATE_SET_MISSING: ClosetErrorDefinition(
        code=METADATA_NORMALIZATION_CANDIDATE_SET_MISSING,
        status_code=422,
        detail="No usable metadata candidate set is available for normalization.",
    ),
    STALE_REVIEW_VERSION: ClosetErrorDefinition(
        code=STALE_REVIEW_VERSION,
        status_code=409,
        detail="The review payload is stale. Refresh the item and try again.",
    ),
    INVALID_REVIEW_MUTATION: ClosetErrorDefinition(
        code=INVALID_REVIEW_MUTATION,
        status_code=422,
        detail="The requested review mutation is invalid.",
    ),
    REVIEW_NOT_AVAILABLE: ClosetErrorDefinition(
        code=REVIEW_NOT_AVAILABLE,
        status_code=409,
        detail="This closet item is not available in the review flow.",
    ),
    RETRY_NOT_AVAILABLE: ClosetErrorDefinition(
        code=RETRY_NOT_AVAILABLE,
        status_code=409,
        detail="No retryable review step is currently available for this closet item.",
    ),
    REVIEW_SUGGESTION_MISSING: ClosetErrorDefinition(
        code=REVIEW_SUGGESTION_MISSING,
        status_code=409,
        detail="No usable suggestion is available for this field.",
    ),
}


class ClosetDomainError(Exception):
    def __init__(self, *, code: str, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.status_code = status_code
        self.detail = detail


def build_error(
    code: str,
    *,
    detail: str | None = None,
    status_code: int | None = None,
) -> ClosetDomainError:
    definition = ERROR_DEFINITIONS[code]
    return ClosetDomainError(
        code=code,
        status_code=status_code or definition.status_code,
        detail=detail or definition.detail,
    )
