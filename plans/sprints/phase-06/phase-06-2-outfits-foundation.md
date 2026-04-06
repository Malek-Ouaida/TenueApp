# Phase 06 Sprint 2 — Outfits Foundation

## Summary

Implement Sprint 2 as a backend-only slice in `apps/api`, assuming Sprint 1 is the existing wear logging foundation. Deliver reusable outfits, outfit list/detail/filter/archive/favorite flows, create-outfit-from-wear-log, and the minimum wear-log extension needed to support `saved_outfit` logging. Do not add insights, lookbooks, outfit image upload, tags, text search, AI outfit generation, or web/mobile UI work.

## Implementation Changes

### 1. Schema and migration

- Add Alembic revision `0010_phase_06_outfits_foundation.py`.
- Create `outfits` with `id`, `user_id`, `title`, `notes`, `occasion`, `season`, `source`, `is_favorite`, `archived_at`, `created_at`, `updated_at`.
- Create `outfit_items` with `id`, `outfit_id`, `closet_item_id`, `role`, `layer_index`, `sort_index`, `is_optional`, `created_at`, plus unique `(outfit_id, closet_item_id)`.
- Alter `wear_logs` to add nullable `outfit_id` FK to `outfits.id` with `ON DELETE SET NULL`.
- Alter `wear_log_snapshots` to add nullable `outfit_title_snapshot`.
- Add indexes for `outfits(user_id, archived_at, updated_at, id)`, `outfit_items(outfit_id, sort_index)`, and `wear_logs(outfit_id)`.

### 2. Domain layout and service boundaries

- Keep phase-06 code inside the existing wear package; add `Outfit`, `OutfitItem`, and `OutfitSource` to the current SQLAlchemy models.
- Add an `OutfitService`; keep `WearService` focused on wear logs and only extend it for `saved_outfit` creation plus linked-outfit read data.
- Keep persistence in the existing wear repository layer instead of introducing a new top-level domain package in this sprint.
- Reuse the current closet projection and processed-image hydration helpers so outfit cards and wear-log cards render consistently.

### 3. Outfit write behavior

- `POST /outfits` creates a manual outfit from confirmed, user-owned, non-archived closet items only.
- `PATCH /outfits/{outfit_id}` supports partial metadata updates and full composition replacement when `items` is present; normalize `sort_index` server-side to `0..n-1`.
- `POST /outfits/{outfit_id}/archive` soft-archives the outfit; archived outfits remain readable but are excluded from list results by default and cannot be used for new wear logging.
- `is_favorite` is updated through `PATCH /outfits/{outfit_id}`; do not add a separate favorite endpoint in Sprint 2.
- `title` stays nullable but uses the same trim and `255`-character validation as closet draft titles; `notes` reuse the current `1000`-character wear-log limit.
- `occasion` reuses the existing wear-context vocabulary and `season` reuses the current closet taxonomy season values.

### 4. Outfit composition and derivation rules

- Outfit items reuse the current role vocabulary `top|bottom|dress|outerwear|shoes|bag|accessory|other`.
- `layer_index` is optional and preserved as sent; `is_optional` defaults to `false`.
- `POST /outfits/from-wear-log/{wear_log_id}` copies the current persisted `wear_log_items` composition into a new outfit, sets `source=derived_from_wear_log`, carries over `role` and normalized order, defaults all `is_optional=false`, and does not mutate the source wear log.
- Creating an outfit from a wear log must revalidate every referenced closet item as still user-owned, confirmed, and non-archived.
- Do not add outfit snapshot tables in Sprint 2. Outfits are intentionally mutable reusable compositions, and cover imagery is derived from the first active outfit item’s processed image.

### 5. Wear-log compatibility extension

- Expand `POST /wear-logs` to support `mode="manual_items"` and `mode="saved_outfit"`.
- `mode="saved_outfit"` requires `outfit_id`, copies `outfit_items` into `wear_log_items`, sets `wear_logs.outfit_id`, sets `source=saved_outfit`, and stores `outfit_title_snapshot`.
- Extend wear detail, timeline, and calendar responses with outfit display data.
- Keep `PATCH /wear-logs/{id}` as a direct historical-edit endpoint. It must not accept `mode` or `outfit_id`.
- If a saved-outfit wear log later receives manual `items` through `PATCH /wear-logs/{id}`, replace `wear_log_items`, clear `outfit_id`, clear `outfit_title_snapshot`, and set `source=mixed`.
- Metadata-only wear-log edits keep any existing outfit linkage intact.

### 6. Read models and pagination

- `GET /outfits` is cursor-paginated, ordered by `updated_at desc, id desc`, with filters `occasion`, `season`, `is_favorite`, `source`, and `include_archived=false` by default.
- `GET /outfits/{outfit_id}` returns metadata, derived cover image, and hydrated item cards using current closet projections and processed images.
- Calendar and timeline reads continue to come from wear logs, not outfits; outfit data is only supplemental display data.
- Do not add list search, outfit analytics, similarity ranking, or cached aggregates in this sprint.

## Public Interfaces

- New routes:
  - `POST /outfits`
  - `GET /outfits`
  - `GET /outfits/{outfit_id}`
  - `PATCH /outfits/{outfit_id}`
  - `POST /outfits/{outfit_id}/archive`
  - `POST /outfits/from-wear-log/{wear_log_id}`
- New write contracts:
  - `OutfitItemWriteRequest`
  - `OutfitCreateRequest`
  - `OutfitUpdateRequest`
  - `CreateOutfitFromWearLogRequest`
- Wear contract changes:
  - `WearLogCreateRequest` supports both manual-item and saved-outfit shapes
  - wear detail adds `linked_outfit`
  - wear timeline and calendar day summary add `outfit_title`

## Test Plan

- API tests for outfit auth, manual create, detail, filtered list, cursor pagination, metadata patch, favorite patch, and archive behavior.
- Validation tests for duplicate outfit item IDs, cross-user item references, unconfirmed or archived closet items, invalid `occasion` or `season`, and archived-outfit reuse rejection.
- Composition tests for normalized sort ordering, item removal and replacement via `PATCH`, and preservation of `layer_index` and `is_optional`.
- Create-from-wear-log tests for successful copy, `source=derived_from_wear_log`, no mutation of the source wear log, and rejection when the wear log contains now-ineligible closet items.
- Wear-log regression tests for `mode="saved_outfit"`, copied `wear_log_items`, stored `outfit_id`, stored `outfit_title_snapshot`, linked-outfit calendar and timeline data, and the `PATCH /wear-logs/{id}` rule that manual item replacement clears outfit linkage and flips the source to `mixed`.
- Verification commands:
  - `scripts/api/test.sh`
  - `scripts/api/lint.sh`
  - `scripts/api/typecheck.sh`

## Assumptions

- Sprint 2 remains backend-only.
- Archive, not hard delete, is the only outfit removal path in MVP.
- Outfit cover images are derived, not separately uploaded or stored.
- No new global error envelope or cross-phase repository refactor is part of this sprint.
- Insights, lookbooks, AI-suggested outfits, and broader profile analytics remain out of scope for this sprint.
