# Phase 04 Sprint 1 — Closet Schema and Lifecycle

## Summary

Create `/Users/malekouaida/Desktop/Projects/TenueApp/plans/sprints/phase-04/phase-04-1-closet-schema-and-lifecycle.md` with this plan, then implement Sprint 1 as a backend-only slice in `apps/api`.
This sprint establishes the closet domain foundation only: schema, lifecycle enforcement, taxonomy contract, worker skeleton, error catalog, and `GET /closet/metadata/options`.
Do not include upload finalization, provider integrations, image processing, extraction, browse/search/detail, or any web/mobile work in this sprint.

## Implementation Changes

### 1. Closet schema and migration

Add a new Alembic revision after `0002_phase_03_auth_foundation` that creates these tables:

- `closet_items`
  Purpose: the root item record.
  Columns: `id`, `user_id`, `lifecycle_status`, `processing_status`, `review_status`, `primary_image_id`, `title`, `failure_summary`, `confirmed_at`, `created_at`, `updated_at`.

- `media_assets`
  Purpose: object-storage-backed files used by closet items.
  Columns: `id`, `user_id`, `bucket`, `key`, `mime_type`, `file_size`, `checksum`, `width`, `height`, `source_kind`, `is_private`, `created_at`, `updated_at`.

- `closet_item_images`
  Purpose: link an item to one or more assets with a role.
  Columns: `id`, `closet_item_id`, `asset_id`, `role`, `position`, `is_active`, `created_at`.

- `processing_runs`
  Purpose: one logical pipeline attempt per item/run type.
  Columns: `id`, `closet_item_id`, `run_type`, `status`, `retry_count`, `started_at`, `completed_at`, `failure_code`, `failure_payload`, `created_at`, `updated_at`.

- `provider_results`
  Purpose: append-only raw provider payload storage.
  Columns: `id`, `closet_item_id`, `processing_run_id`, `provider_name`, `provider_model`, `provider_version`, `task_type`, `status`, `raw_payload`, `created_at`.

- `closet_item_field_candidates`
  Purpose: raw or normalized AI suggestions before trust materialization.
  Columns: `id`, `closet_item_id`, `field_name`, `raw_value`, `normalized_candidate`, `confidence`, `provider_result_id`, `applicability_state`, `conflict_notes`, `created_at`.

- `closet_item_field_states`
  Purpose: one current trust-aware state per field.
  Columns: `id`, `closet_item_id`, `field_name`, `canonical_value`, `source`, `confidence`, `review_state`, `applicability_state`, `taxonomy_version`, `created_at`, `updated_at`.

- `closet_item_metadata_projection`
  Purpose: flattened queryable metadata for future browse/filter/detail.
  Columns: `id`, `closet_item_id`, `user_id`, `taxonomy_version`, `title`, `category`, `subcategory`, `primary_color`, `secondary_colors`, `material`, `pattern`, `brand`, `style_tags`, `occasion_tags`, `season_tags`, `confirmed_at`, `updated_at`.

- `closet_item_audit_events`
  Purpose: immutable history of significant item actions.
  Columns: `id`, `closet_item_id`, `actor_user_id`, `actor_type`, `event_type`, `payload`, `created_at`.

- `closet_item_similarity_edges`
  Purpose: future explainable duplicate/similar relationships.
  Columns: `id`, `item_a_id`, `item_b_id`, `similarity_type`, `score`, `signals_json`, `decision_status`, `created_at`, `updated_at`.

- `closet_jobs`
  Purpose: durable worker skeleton queue for later sprints.
  Columns: `id`, `closet_item_id`, `job_kind`, `status`, `available_at`, `locked_at`, `locked_by`, `attempt_count`, `max_attempts`, `payload`, `last_error_code`, `last_error_detail`, `created_at`, `updated_at`.

Use portable SQLAlchemy types:
- status fields as string-backed enums with `native_enum=False`
- structured payloads and tag lists as `JSON`
- UUID PK/FK fields throughout

Add only the indexes needed now and for the next 2-3 sprints:
- `closet_items(user_id, lifecycle_status, review_status)`
- `media_assets(checksum)`
- `closet_item_images(closet_item_id, role)`
- unique `closet_item_field_states(closet_item_id, field_name)`
- unique `closet_item_metadata_projection(closet_item_id)`
- `closet_item_metadata_projection(user_id, category, subcategory, primary_color)`
- unique canonical pair on `closet_item_similarity_edges(item_a_id, item_b_id, similarity_type)`
- `closet_jobs(status, available_at)`

### 2. Domain module and lifecycle rules

Create `app/domains/closet` with `models.py`, `repository.py`, `service.py`, `taxonomy.py`, `errors.py`, and `worker.py`.

Define these lifecycle enums and keep them fixed in Sprint 1:
- `lifecycle_status`: `draft`, `processing`, `review`, `confirmed`, `archived`
- `processing_status`: `pending`, `running`, `completed`, `completed_with_issues`, `failed`
- `review_status`: `needs_review`, `ready_to_confirm`, `confirmed`

Implement service-level transition enforcement:
- item creation starts at `draft` + `pending` + `needs_review`
- `draft -> processing` allowed only when a primary image exists
- `processing -> review` allowed when a run finishes in `completed`, `completed_with_issues`, or `failed`
- `review -> confirmed` allowed only when the item has an active primary image plus confirmed values for `category` and `subcategory`
- `confirmed -> archived` allowed
- direct `draft -> confirmed` and `processing -> confirmed` are rejected
- `archived` is terminal for Sprint 1

Implement `ClosetLifecycleService` methods for:
- creating the initial item aggregate
- attaching or changing the primary asset reference
- updating processing state
- recomputing review readiness
- confirming an item
- archiving an item
- recording audit events

Use string field names, not DB enums, for trust-layer fields so future metadata expansion does not require schema churn.
Initial supported field names:
- `title`
- `category`
- `subcategory`
- `colors`
- `material`
- `pattern`
- `brand`
- `style_tags`
- `occasion_tags`
- `season_tags`

### 3. Taxonomy contract and metadata options endpoint

Make taxonomy v1 code-backed, not DB-managed.
Add `taxonomy.py` with a single version constant, recommended as `closet-taxonomy-v1`.

Expose `GET /closet/metadata/options` under a new `closet` router.
Keep it authenticated with the existing `CurrentUser` dependency.

Response contract:
- `taxonomy_version`
- `required_confirmation_fields`: `["category", "subcategory"]`
- `lifecycle_statuses`
- `processing_statuses`
- `review_statuses`
- `categories`: each category includes its allowed subcategories
- `colors`
- `materials`
- `patterns`
- `style_tags`
- `occasion_tags`
- `season_tags`

Use the exact MVP taxonomy from the master plan:
- categories: `tops`, `bottoms`, `dresses`, `outerwear`, `shoes`, `bags`, `accessories`
- subcategories exactly as listed in the phase doc
- controlled colors/materials/patterns/tags exactly as listed in the phase doc

### 4. Error catalog and worker skeleton

Add a closet-domain error catalog with stable internal codes:
- `closet_item_not_found`
- `invalid_lifecycle_transition`
- `missing_primary_image`
- `missing_required_confirmation_fields`
- `unsupported_taxonomy_version`
- `invalid_field_name`
- `job_not_claimable`
- `job_retry_exhausted`

Keep HTTP responses aligned with the current app style for now.
Do not introduce a new global error envelope in this sprint.

Implement a minimal durable worker skeleton:
- `enqueue_job`
- `claim_next_job`
- `mark_job_running`
- `mark_job_completed`
- `mark_job_failed`
- `release_job_for_retry`

Define job kinds now but do not implement handlers yet:
- `upload_validation`
- `asset_promotion`
- `image_processing`
- `metadata_extraction`
- `normalization_projection`
- `similarity_recompute`

Add a `run_once(worker_name: str)` entrypoint in `worker.py`.
It should safely claim one job, dispatch only if a handler exists, and otherwise fail the job with a stable unsupported-handler error.
Do not auto-start a background process from the API app in Sprint 1.

## Public Interfaces

New API:
- `GET /closet/metadata/options`

New internal contracts:
- closet lifecycle enums
- trust-layer field-state model
- taxonomy version constant
- durable `closet_jobs` queue contract
- closet domain error codes

## Test Plan

Add or update tests to cover:

- metadata options endpoint requires authentication
- metadata options endpoint returns the expected taxonomy version and required confirmation fields
- metadata options endpoint returns the full category-to-subcategory mapping from taxonomy v1
- lifecycle service allows `draft -> processing -> review -> confirmed`
- lifecycle service rejects `draft -> confirmed`
- lifecycle service rejects confirmation when `category` or `subcategory` is missing
- lifecycle service marks `review_status` as `ready_to_confirm` only when minimum confirmation requirements are satisfied
- archived items cannot be transitioned again
- unique field-state enforcement prevents duplicate current states for the same item/field
- job queue claim only returns jobs whose status and `available_at` make them claimable
- audit events are recorded for confirm and archive actions

Verification commands when executing:
- `scripts/api/test.sh`
- `scripts/api/lint.sh`
- `scripts/api/typecheck.sh`

## Assumptions and Defaults

- Sprint 1 is intentionally backend-only.
- The sprint doc file should be named `/Users/malekouaida/Desktop/Projects/TenueApp/plans/sprints/phase-04/phase-04-1-closet-schema-and-lifecycle.md`.
- Taxonomy is static code in Sprint 1 and versioned through a constant plus API response, not through admin-editable tables.
- `GET /closet/metadata/options` is authenticated even though the payload is global.
- `media_assets` remains owned by the closet slice for now; do not generalize it into a shared media platform yet.
- Worker support is durable but skeletal; no provider calls, no daemon supervision, and no upload flow are part of this sprint.
- The existing FastAPI error shape stays in place; only the closet domain internals gain stable error codes in this sprint.
