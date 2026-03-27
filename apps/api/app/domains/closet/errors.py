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
