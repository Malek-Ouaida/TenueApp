# Tenue — Usage Intelligence Backend Master Roadmap

## Purpose of this document

This document is the **master backend roadmap and planning spec** for the next major Tenue phase after the completed Closet Intelligence Foundation. It is written to be given directly to Codex so it can produce a clean backend implementation plan before writing code.

This phase should be treated as the bridge between:

* **closet truth** (what the user owns)
* **behavior truth** (what the user actually wears)
* **style intelligence** (what the system can infer, explain, and recommend later)

The backend must be designed so that future phases like AI Stylist, Should-I-Buy, Shop-the-Look, and Try-On can build on it without schema rewrites or broken domain boundaries.

---

# 1. Phase name

## Phase 06: Usage Intelligence Foundation

This phase is not primarily about social features or a Pinterest-like lookbook. The product center of gravity is:

* a **profile-level wear calendar / style diary**
* **daily worn look logging**
* **recognized worn items mapped back to confirmed closet items**
* **stats and insights generated from confirmed wear history**
* **reusable outfits built on top of real wear behavior**

The backend should model the system accordingly.

---

# 2. Core product thesis for this phase

Tenue should evolve from a closet intelligence system into a wardrobe behavior system.

The app must be able to answer:

* What did the user actually wear on a given day?
* Which closet items were involved in that worn look?
* Which items are heavily used, neglected, repeated, or stale?
* Which outfit formulas recur in the user’s life?
* How can this behavioral history feed future stylistic and purchase decisions?

This phase should produce the backend truth layer for:

* **daily look history**
* **wear frequency**
* **item recency**
* **outfit repetition**
* **category usage**
* **closet rotation quality**

---

# 3. Recommended implementation order

Codex should plan and implement the phase in this exact order:

1. **Wear logging foundation**
2. **Outfits foundation**
3. **Insights and stats foundation**
4. **Lookbook foundation**

## Why this order

### Wear logging first

Wear logging is the behavioral backbone and the true source of trust for analytics. The profile calendar should read from wear logs, not from outfits.

### Outfits second

Outfits are reusable templates / compositions built from confirmed closet items. They should support wear logging, but should not replace it.

### Insights third

Insights depend on persisted wear events and wear-linked closet items. They should not be built from assumptions or inferred UI state.

### Lookbook last

Lookbook is a curation / inspiration domain, not the core behavioral truth layer. It can come later without blocking the rest of the product.

---

# 4. Phase objective

Deliver the backend foundation so that an authenticated user can:

* log what they wore on a given day
* attach a daily outfit photo if desired
* manually select worn closet items or log from a saved outfit
* later support AI-detected worn-item matching through the same domain model
* browse their wear history in a calendar/timeline-friendly way
* save reusable outfits from closet items
* view explainable insights and stats based on confirmed wear data
* optionally organize saved looks/inspirations in lookbooks later

**Done for the phase means:**
An authenticated user can create daily wear logs tied to dates, confirm which closet items were worn, browse wear history, save and reuse outfits, and retrieve insight endpoints whose results are traceable to confirmed wear log items.

---

# 5. Product and architecture principles

These are non-negotiable.

## 5.1 Only confirmed closet items participate

Only **confirmed closet items** may be referenced by:

* outfits
* wear log items
* insight calculations

No draft/unconfirmed closet item should appear in usage intelligence tables.

## 5.2 Wear logs are the source of behavioral truth

Stats must come from persisted wear events, not from outfit existence or user favorites.

## 5.3 Outfits and worn looks are related but not identical

* **Outfit** = reusable structured combination of closet items
* **Wear log** = record that on a specific date the user wore an outfit or a set of items

A wear log may reference an outfit, but should still persist its own worn-item truth.

## 5.4 Analytics must be explainable

Every insight should be traceable back to:

* wear logs
* wear log items
* closet items
* optionally outfit references or snapshots

## 5.5 AI detection must be confirmable

Future photo detection and closet matching should plug into this phase, but stats must only use **confirmed** wear log items, not raw AI guesses.

## 5.6 Keep service-layer boundaries clean

Follow existing Tenue conventions:

* FastAPI routers only handle HTTP concerns
* business logic lives in domain services
* persistence logic lives in repositories
* models stay persistence-focused
* cursor pagination everywhere appropriate
* Pydantic v2 / SQLAlchemy 2.x style consistency

## 5.7 Mobile-first but backend-clean

Design response contracts to support:

* mobile calendar screens
* day detail screens
* outfit builder flows
* profile summary cards
* future web experience

No mobile-only hacks in the domain model.

---

# 6. Domain overview

This phase should introduce four domain areas.

## 6.1 Wear logging domain

The central behavioral system.

## 6.2 Outfit domain

Reusable combinations built from confirmed closet items.

## 6.3 Insight domain

Read-only aggregation layer built from wear truth.

## 6.4 Lookbook domain

Optional curation/inspiration layer. Lower priority.

---

# 7. Domain model — canonical entities

## 7.1 Wear logs

Represents a daily logged look / wear event.

### Table: `wear_logs`

Suggested fields:

* `id` UUID PK
* `user_id` UUID FK users
* `wear_date` DATE NOT NULL
* `outfit_id` UUID nullable FK outfits
* `source` enum (`manual_items`, `saved_outfit`, `photo_detected`, `mixed`)
* `photo_storage_key` nullable
* `photo_url` nullable derived/response only if desired
* `notes` nullable text
* `context` nullable enum or freeform string (example: work, casual, event, travel)
* `is_confirmed` boolean default true for manual flows, false/true depending on future AI flow design
* `created_at`
* `updated_at`
* `deleted_at` nullable soft delete if desired

### Notes

* There should usually be at most one primary wear log per user per date in MVP, unless deliberate support for multiple looks/day is added.
* If multiple logs/day are allowed later, support a `part_of_day` or `sequence_index` field. For MVP, keep it simpler unless product explicitly requires multiple daily looks.

---

## 7.2 Wear log items

Represents the confirmed closet items that were worn in a specific wear log.

### Table: `wear_log_items`

Suggested fields:

* `id` UUID PK
* `wear_log_id` UUID FK wear_logs
* `closet_item_id` UUID FK confirmed closet items
* `source` enum (`manual`, `from_outfit`, `ai_matched`, `manual_override`)
* `match_confidence` nullable numeric
* `sort_index` nullable int
* `role` nullable string/enum (`top`, `bottom`, `outerwear`, `dress`, `shoes`, `bag`, `accessory`, etc.)
* `created_at`
* unique constraint on (`wear_log_id`, `closet_item_id`) for MVP unless same item repetition inside one log is explicitly required

### Notes

This is the most important analytics table in the phase. Most item-level stats will read from this table.

---

## 7.3 Wear log snapshots

Prevents historical drift if the referenced outfit changes later.

### Table: `wear_log_snapshots`

Suggested fields:

* `wear_log_id` UUID PK/FK wear_logs
* `outfit_title_snapshot` nullable
* `items_snapshot_json` JSONB
* `source_snapshot_json` JSONB nullable
* `created_at`

### Purpose

If a user logs a saved outfit on April 6, then later edits the original outfit, the historical wear record should remain stable for analytics and replay.

MVP can start with a lightweight snapshot of item IDs + key metadata.

---

## 7.4 Outfits

Reusable combinations of confirmed closet items.

### Table: `outfits`

Suggested fields:

* `id` UUID PK
* `user_id` UUID FK users
* `title` nullable but strongly recommended
* `notes` nullable text
* `occasion` nullable enum/string
* `season` nullable enum/string
* `cover_image_storage_key` nullable
* `source` enum (`manual`, `derived_from_wear_log`, `ai_suggested` future)
* `is_favorite` boolean default false
* `archived_at` nullable
* `created_at`
* `updated_at`

---

## 7.5 Outfit items

Links closet items to an outfit composition.

### Table: `outfit_items`

Suggested fields:

* `id` UUID PK
* `outfit_id` UUID FK outfits
* `closet_item_id` UUID FK confirmed closet items
* `role` nullable enum/string
* `layer_index` nullable int
* `sort_index` int default 0
* `is_optional` boolean default false
* `created_at`
* unique constraint on (`outfit_id`, `closet_item_id`) for MVP

### Notes

Store composition metadata from day one. Do not reduce outfits to unstructured item lists.

---

## 7.6 Lookbooks

Optional lower-priority curation layer.

### Table: `lookbooks`

Suggested fields:

* `id` UUID PK
* `user_id` UUID FK users
* `title`
* `description` nullable
* `cover_image_storage_key` nullable
* `sort_index` nullable
* `archived_at` nullable
* `created_at`
* `updated_at`

### Table: `lookbook_entries`

Suggested fields:

* `id` UUID PK
* `lookbook_id` UUID FK lookbooks
* `entry_type` enum (`outfit`, `image`, `note`, `wear_log` optional)
* `outfit_id` nullable
* `wear_log_id` nullable if supporting saved daily looks later
* `image_storage_key` nullable
* `note_text` nullable
* `caption` nullable
* `sort_index` int default 0
* `created_at`

### Notes

This should remain distinct from wear logs. Lookbooks are curated collections, not the source of behavioral truth.

---

# 8. Recommended sprint breakdown

## Sprint 1 — Wear logging foundation

This is the highest priority sprint.

### Scope

Build the daily wear logging backbone and profile-calendar data source.

### User outcomes

* log a worn look for a specific date
* log by selecting closet items directly
* log from an existing saved outfit
* optionally attach a daily outfit photo
* edit a wear log
* delete a wear log
* browse wear history by date range
* fetch calendar-friendly day summaries

### Backend deliverables

* migrations for `wear_logs`, `wear_log_items`, optional `wear_log_snapshots`
* service layer for create/update/delete/list/read wear logs
* validation that only confirmed closet items are accepted
* logging from saved outfit copies outfit items into wear_log_items
* snapshots on wear creation from saved outfit or manual composition
* cursor-paginated wear history endpoint
* date-range endpoint optimized for calendar usage
* tests for write flows and edge cases

### Key rules

* if user logs from outfit, persist wear_log_items immediately
* do not compute worn items lazily from outfit_id later
* historical logs should remain stable even if outfit changes later

---

## Sprint 2 — Outfits foundation

Build reusable saved combinations after the wear backbone exists.

### User outcomes

* create an outfit from confirmed closet items
* edit, reorder, remove outfit items
* browse outfits
* filter outfits
* favorite or archive outfits
* optionally create outfit from an existing wear log

### Backend deliverables

* migrations for `outfits`, `outfit_items`
* outfit CRUD service layer
* composition and reorder behavior
* create-outfit-from-wear-log flow
* outfit browse/detail endpoints
* filters by occasion/season/favorite/tag if implemented
* tests

### Important relationship

A wear log may optionally point to an outfit, and a wear log may be used to generate a new outfit, but neither should erase the distinction between reusable composition and historical event.

---

## Sprint 3 — Insights and stats foundation

Build explainable read models on top of wear truth.

### User outcomes

* see an overview of usage
* see item-level wear frequency
* see most/least worn items
* see stale / never-worn items
* see category usage
* see most worn outfits or repeated formulas
* retrieve calendar/timeline summaries

### Backend deliverables

* insight service layer
* performant aggregate queries
* response contracts for overview, items, outfits, categories, timeline
* optional light caching if necessary
* tests that validate query correctness against seeded wear history

### Important rule

No fake insights. All outputs must be traceable to confirmed wear_log_items.

---

## Sprint 4 — Lookbook foundation

Optional lower-priority curation and inspiration layer.

### User outcomes

* create a lookbook
* add outfit/image/note entries
* browse and reorder entries
* keep lookbooks private for now

### Backend deliverables

* lookbook schema and CRUD
* entry model and reorder support
* tests

---

# 9. API design recommendations

The exact route naming can follow project conventions, but Codex should keep the surface area clean and explicit.

## 9.1 Wear logging routes

Suggested routes:

* `POST /wear-logs`
* `GET /wear-logs`
* `GET /wear-logs/{wear_log_id}`
* `PATCH /wear-logs/{wear_log_id}`
* `DELETE /wear-logs/{wear_log_id}`
* `GET /wear-logs/calendar`
* `GET /wear-logs/timeline`
* `POST /wear-logs/{wear_log_id}/confirm` if explicit confirmation state is needed

### Suggested `POST /wear-logs` modes

The create request should support:

1. `manual_items`
2. `saved_outfit`
3. future-compatible `photo_detected`

Example request patterns:

* wear date + item IDs
* wear date + outfit ID
* wear date + photo attachment flow + matched item candidates later

### Calendar endpoint purpose

Return day summaries across a date range with enough metadata for mobile profile calendar rendering.

Example response shape per day:

* date
* has_log
* wear_log_id
* thumbnail
* item_count
* outfit_title or fallback
* confirmation state

---

## 9.2 Outfit routes

Suggested routes:

* `POST /outfits`
* `GET /outfits`
* `GET /outfits/{outfit_id}`
* `PATCH /outfits/{outfit_id}`
* `DELETE /outfits/{outfit_id}` or archive
* `POST /outfits/{outfit_id}/items`
* `PATCH /outfits/{outfit_id}/items/reorder`
* `DELETE /outfits/{outfit_id}/items/{outfit_item_id}`
* `POST /outfits/{outfit_id}/favorite`
* `POST /outfits/{outfit_id}/archive`
* `POST /outfits/from-wear-log/{wear_log_id}`

---

## 9.3 Insight routes

Suggested routes:

* `GET /insights/overview`
* `GET /insights/items`
* `GET /insights/outfits`
* `GET /insights/categories`
* `GET /insights/timeline`
* `GET /insights/stale-items`
* `GET /insights/never-worn`

### MVP metrics to support

* total wears in current month
* current streak / longest streak if feasible
* most worn items
* least worn items
* never worn items
* stale items by threshold days
* category usage counts
* most worn outfits
* repeated outfit formulas if doable
* recent wear activity summaries

---

## 9.4 Lookbook routes

Suggested routes:

* `POST /lookbooks`
* `GET /lookbooks`
* `GET /lookbooks/{lookbook_id}`
* `PATCH /lookbooks/{lookbook_id}`
* `DELETE /lookbooks/{lookbook_id}`
* `POST /lookbooks/{lookbook_id}/entries`
* `PATCH /lookbooks/{lookbook_id}/entries/reorder`
* `DELETE /lookbooks/{lookbook_id}/entries/{entry_id}`

---

# 10. Service-layer design

Codex should create clean domain services rather than bloating routers.

## 10.1 Suggested service modules

* `wear_logging_service.py`
* `outfit_service.py`
* `insight_service.py`
* `lookbook_service.py`
* optional `wear_matching_service.py` placeholder for future AI-detected item matching

## 10.2 Suggested responsibilities

### Wear logging service

* create wear log
* validate closet item eligibility
* hydrate from saved outfit
* persist wear_log_items
* create snapshot
* update wear log
* replace wear log items safely
* list and date-filter wear logs
* build calendar summaries

### Outfit service

* create/update outfit
* validate confirmed closet item usage
* manage composition ordering
* build outfit from wear log
* browse/filter/favorite/archive

### Insight service

* read-only query orchestration
* overview metrics
* item usage metrics
* outfit usage metrics
* stale/never-worn logic
* category distributions
* recency-based summaries

### Lookbook service

* CRUD lookbooks
* add/remove/reorder mixed entries

---

# 11. Repository-layer guidance

Codex should preserve existing repository patterns and keep persistence logic isolated.

Suggested repository modules:

* `wear_log_repository.py`
* `outfit_repository.py`
* `insight_repository.py` or query methods in insight service if preferred
* `lookbook_repository.py`

Important repository concerns:

* date-range filtering for calendar view
* cursor pagination for history and list endpoints
* efficient joins between wear_log_items and closet_items
* careful soft-delete handling if used
* stable ordering for outfits and lookbooks

---

# 12. Photo-based daily logging hooks

This phase should not fully implement advanced vision workflows unless explicitly desired, but the data model must be ready.

## Future-compatible flow

1. user uploads daily outfit photo
2. image processing / moderation / normalization if needed
3. AI extracts visible garment candidates
4. matching logic proposes closet item matches
5. user confirms/corrects
6. wear log is finalized with confirmed wear_log_items

## Backend prep needed now

* source enums should allow `photo_detected`
* wear log items should support confidence metadata
* confirmation state should be representable
* a wear log can exist before full confirmation if future async flow demands it

### Recommended MVP stance

Even if async photo-detected logging is not fully built now, do not block future integration with a schema that assumes only manual entry forever.

---

# 13. Insight design philosophy

Insights should feel useful, explainable, and future-ready.

## 13.1 First-wave insight categories

### Item usage

* wear count per item
* last worn date
* first worn date
* stale items
* never worn items

### Outfit usage

* wear count per outfit
* last worn date
* top repeated outfits

### Category usage

* category wear totals
* category recency
* underused categories

### Time patterns

* wears per week / month
* streak basics
* gaps in logging

### Closet health

* percentage of closet worn this month
* top rotation carriers
* underused closet segment size

## 13.2 Explainability rule

Every metric should be explainable with drill-down potential later.
Do not build vague “smart scores” until the user can trust the behavioral base.

---

# 14. Calendar/profile backend requirements

Because the profile will visualize daily looks in calendar form, Codex should explicitly plan for a calendar read model.

## Calendar endpoint requirements

Must support:

* date range input
* efficient month loading
* per-day status summary
* thumbnail/cover info
* wear_log_id per populated day
* lightweight enough for mobile

## Suggested response fields per day

* `date`
* `has_wear_log`
* `wear_log_id`
* `cover_image_url` or thumbnail
* `item_count`
* `outfit_title`
* `source`
* `is_confirmed`

## Day detail endpoint requirements

The wear log detail endpoint should provide:

* wear metadata
* linked outfit if any
* worn items with enough closet metadata to render chips/cards
* photo if present
* notes/context
* snapshot or composition detail as needed

---

# 15. Validation and domain rules

Codex must enforce these at the service layer.

## Required validations

* wear log date belongs to valid date format and user ownership checks pass
* outfit ownership checks
* closet item ownership checks
* closet items must be confirmed / eligible
* duplicate closet_item_ids inside same wear log should be blocked or normalized
* duplicate closet_item_ids inside same outfit should be blocked for MVP
* updating a wear log should replace item composition atomically
* soft-deleted/archived entities must be handled consistently

## Ownership and trust

Every write path must validate that all referenced entities belong to the authenticated user.

---

# 16. Suggested enums / controlled vocabularies

Codex may adjust naming to fit existing conventions, but should preserve semantics.

## Wear log source

* `manual_items`
* `saved_outfit`
* `photo_detected`
* `mixed`

## Wear log item source

* `manual`
* `from_outfit`
* `ai_matched`
* `manual_override`

## Outfit source

* `manual`
* `derived_from_wear_log`
* `ai_suggested`

## Optional context values

* `casual`
* `work`
* `event`
* `travel`
* `gym`
* `lounge`

Keep enums lean unless product already needs more.

---

# 17. Performance expectations

The backend should remain simple, but Codex should plan for reasonable scale and responsiveness.

## Query expectations

* calendar reads should be efficient by date range and user_id
* item usage aggregates should avoid unnecessary N+1 queries
* outfit list/detail reads should join composition efficiently
* insight endpoints should be serviceable off live SQL queries for MVP

## Index suggestions

Consider indexes on:

* `wear_logs (user_id, wear_date)`
* `wear_log_items (wear_log_id)`
* `wear_log_items (closet_item_id)`
* `outfits (user_id, created_at)`
* `outfit_items (outfit_id)`
* `lookbooks (user_id, created_at)`

Do not prematurely over-engineer materialized views unless query profiles justify it.

---

# 18. Testing expectations

This phase should follow the same quality bar as the closet phase.

## Must-have tests

### Wear logging tests

* create wear log from manual items
* create wear log from saved outfit
* reject unconfirmed closet items
* reject cross-user references
* update wear log composition
* delete wear log
* calendar date-range read
* snapshot stability on outfit edit

### Outfit tests

* create outfit
* reorder items
* remove item
* favorite/archive behavior
* create outfit from wear log

### Insight tests

* correct counts for most worn / least worn
* stale item correctness
* never-worn correctness
* category usage correctness
* outfit wear count correctness

### Lookbook tests

* create lookbook
* add mixed entries
* reorder entries

---

# 19. Recommended deliverable style for Codex

Codex should not start by writing implementation immediately. It should first produce a planning deliverable with the following sections:

1. **Phase summary**
2. **Scope and non-goals**
3. **Domain model**
4. **Schema changes / migrations**
5. **Service-layer plan**
6. **Repository-layer plan**
7. **Route plan**
8. **Validation rules**
9. **Response contract design**
10. **Testing plan**
11. **Open decisions / tradeoffs**
12. **Suggested implementation order by PR/sprint**

---

# 20. Important non-goals for this phase

To avoid scope creep, Codex should treat these as explicitly out of scope unless later requested:

* public social feed features
* likes/comments/follows
* collaborative outfits/lookbooks
* advanced recommendation ranking
* full AI stylist generation
* should-I-buy decision engine
* marketplace or commerce integrations
* virtual try-on
* heavy ML pipelines beyond placeholder-compatible hooks

This phase is about building the trustworthy usage backbone.

---

# 21. What this phase unlocks next

Codex should keep these future unlocks in mind when making design choices.

## AI Stylist foundation

Needs:

* reusable outfits
* known wear history
* knowledge of overused/underused items
* behavioral preference clues

## Should-I-Buy foundation

Needs:

* closet similarity and duplication from prior phase
* wear frequency and underuse data from this phase
* item recency and closet gap understanding

## Shop-the-Look foundation

Needs:

* outfit composition understanding
* item-level semantic similarity
* style formula awareness

## Try-On foundation

Needs:

* reliable item metadata
* outfit composition
* saved daily looks / profile archive for context

---

# 22. Codex planning prompt

Use the following instruction as the direct planning prompt:

---

You are planning the backend for the next Tenue phase: **Usage Intelligence Foundation**.

Context:

* The Closet Intelligence Foundation is already complete.
* Tenue already supports closet schema/lifecycle, upload/draft flow, image processing, metadata extraction, metadata normalization/trust, confirmation/editing, browse/search/detail, and similarity/duplicate detection.
* Stack and conventions must remain aligned with the existing backend: FastAPI, Pydantic v2, SQLAlchemy 2.x, Postgres, service-layer business logic, repository-layer persistence, cursor pagination, clean HTTP contracts, mobile-first but backend-clean design.
* Only confirmed closet items may participate in outfits, wear logs, and analytics.

Your task is to produce a **backend master plan** for Usage Intelligence Foundation before writing code.

The implementation order must be:

1. Wear logging foundation
2. Outfits foundation
3. Insights and stats foundation
4. Lookbook foundation

Product direction:

* The profile should function as a **wear calendar / style diary**.
* Users should be able to log what they wore on a given date.
* A wear log may be created from manual closet-item selection, from a saved outfit, and later from a photo-detected flow.
* The system must know which confirmed closet items were worn in each log.
* Stats must be built from confirmed wear history, not assumptions.
* Outfits are reusable combinations; wear logs are dated historical events.
* Lookbooks are optional curation and should remain distinct from wear logs.

Planning requirements:

* Define the domain model and propose schema tables/fields for wear logs, wear log items, optional snapshots, outfits, outfit items, lookbooks, and lookbook entries.
* Define service-layer responsibilities and repository boundaries.
* Propose clean route design.
* Define the key validations and ownership/trust rules.
* Design response contracts suitable for mobile profile calendar views, day detail views, outfit builder flows, and insight screens.
* Preserve historical stability when a wear log references an outfit that may later change.
* Make the schema future-compatible with AI-detected outfit photo logging, but do not overbuild ML infrastructure now.
* Keep analytics explainable and traceable to confirmed wear log items.
* Recommend indexes, query patterns, and testing strategy.
* Explicitly call out non-goals and future unlocks.

Output format:
Provide a structured plan with these sections:

1. Phase summary
2. Scope and non-goals
3. Domain model
4. Schema/migration plan
5. Service-layer plan
6. Repository/query plan
7. Route plan
8. Validation and domain rules
9. Response contracts
10. Testing plan
11. Risks/tradeoffs/open decisions
12. PR / sprint implementation order

Important design rules:

* Do not treat outfits and wear logs as the same thing.
* Do not derive analytics from mutable outfit state alone.
* Do not allow draft closet items into usage intelligence.
* Keep the architecture extensible for later AI stylist, should-I-buy, shop-the-look, and try-on phases.

---

# 23. Final recommendation

Codex should begin with planning only, not immediate implementation. The strongest first implementation slice is:

* wear log schema
* create/list/detail/update/delete wear logs
* manual item-based logging
* saved-outfit logging
* calendar range endpoint
* snapshot support
* tests

Then move into reusable outfits, then insights, then lookbooks.

This is the cleanest path to a powerful profile calendar, trustworthy stats, and future styling intelligence.
