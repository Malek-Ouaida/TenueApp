# Phase 04 Sprint 2 — Closet Upload and Draft Flow

## Summary

Implement Sprint 2 as a backend-only slice in `apps/api`, on branch `phase-04/s2-upload-draft`. Deliver authenticated draft creation, private presigned uploads to MinIO, synchronous finalize validation and promotion, and a cursor-paginated pre-confirmation review inbox. Do not add image processing, extraction, confirmation/editing UI, or mobile/web upload surfaces.

## Implementation Changes

### 1. Private upload backbone

- Add `app/core/storage` with a MinIO/S3-compatible adapter using `boto3`, path-style access, presigned `PUT` uploads, `head_object`, copy/promote, and delete helpers.
- Add `Pillow` for decode and dimension validation.
- Use direct presigned `PUT` uploads to the existing private bucket; do not proxy image bytes through FastAPI.
- Upload into a staging prefix first, then validate and promote to an original-media prefix during finalize.
- Keep upload policy code-backed:
  - allowed MIME types: `image/jpeg`, `image/png`, `image/webp`
  - max size: `15 * 1024 * 1024`
  - max dimensions: `8000 x 8000`
  - upload intent TTL: `15 minutes`

### 2. Persistence contracts

- Add migration `0005_phase_04_closet_upload_and_draft_flow.py`.
- Add `closet_upload_intents` with statuses `pending`, `finalized`, `expired`, `failed`.
- Add `closet_idempotency_keys` with unique `(user_id, operation, idempotency_key)`.
- Keep storage keys deterministic:
  - staging: `closet/staging/<user_id>/<item_id>/<intent_id>`
  - originals: `closet/originals/<user_id>/<item_id>/<asset_id>`
- Use `processing_runs` for synchronous `upload_validation` completion records only.

### 3. Closet draft and review APIs

- `POST /closet/drafts`
  - authenticated
  - requires `Idempotency-Key`
  - accepts optional `title`
  - idempotent on successful create
- `GET /closet/drafts/{id}`
  - authenticated
  - returns the pre-confirmation draft workflow resource
- `POST /closet/drafts/{id}/upload-intents`
  - authenticated
  - request: `filename`, `mime_type`, `file_size`, `sha256`
  - returns an existing non-expired pending intent instead of issuing a second one
- `POST /closet/drafts/{id}/uploads/complete`
  - authenticated
  - requires `Idempotency-Key`
  - request: `upload_intent_id`
  - validates object presence, MIME, size, checksum, decodeability, and dimensions
  - atomically creates the asset row, image link, primary image pointer, audit event, and completed `upload_validation` processing run
- `GET /closet/review`
  - authenticated
  - lists all non-confirmed, non-archived items
  - ordered by `updated_at desc, id desc`
  - cursor-paginated with default `20`, max `50`

### 4. Domain behavior and error handling

- Add a dedicated draft/upload service and keep lifecycle transitions in `ClosetLifecycleService`.
- Keep one original image per draft in Sprint 2.
- Keep finalize atomic at the DB level. On DB failure after object promotion, delete the promoted object.
- Do not enqueue image-processing or extraction jobs yet.
- Add stable closet-domain error codes:
  - `upload_intent_not_found`
  - `upload_intent_expired`
  - `upload_already_finalized`
  - `upload_not_present`
  - `upload_checksum_mismatch`
  - `upload_validation_failed`
  - `unsupported_upload_mime_type`
  - `upload_too_large`
  - `upload_dimensions_exceeded`
  - `idempotency_conflict`

## Public Interfaces

- Draft snapshot returns:
  - `id`, `title`, `lifecycle_status`, `processing_status`, `review_status`, `failure_summary`, `has_primary_image`, `created_at`, `updated_at`
- Upload intent response returns:
  - `upload_intent_id`, `expires_at`, `upload.method`, `upload.url`, `upload.headers`
- Review list response returns:
  - `items`, `next_cursor`

## Test Plan

- API tests for draft creation auth, idempotent replay, and idempotency conflict.
- API tests for upload-intent success, ownership rejection, MIME rejection, file-size rejection, invalid checksum format, and primary-image-already-present rejection.
- Finalize tests for success, success replay idempotency, expired intent rejection, missing object, checksum mismatch, invalid image decode, and dimension-cap rejection.
- Persistence tests for `media_assets`, `closet_item_images`, `primary_image_id`, audit events, and completed `upload_validation` runs.
- Review queue tests for exclusion rules and stable cursor pagination.
- One `db_integration` MinIO smoke test for presigned `PUT` upload plus finalize.
- Verification commands:
  - `scripts/api/test.sh`
  - `scripts/api/lint.sh`
  - `scripts/api/typecheck.sh`

## Assumptions

- Sprint 2 remains backend-only.
- Successful create/finalize mutations are idempotent; validation failures are not stored as successful idempotent outcomes.
- HEIC/HEIF stays out of scope.
- A draft with an uploaded original image remains a pre-confirmation workflow item; the review inbox is a query surface, not a lifecycle transition.
