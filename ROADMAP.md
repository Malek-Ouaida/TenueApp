# ROADMAP.md

## Purpose

This file defines the **high-level build order** for Tenue.

It is not a detailed implementation spec.
It exists to keep product development sequenced correctly and to ensure the team and coding agents build the system in the right order.

Detailed execution belongs in:
- `AGENTS.md`
- `ARCHITECTURE.md`
- `plans/phases/phase-*/phase-*.md`

---

## Product direction

Tenue is an **AI-powered closet companion**.

The product is built around one core rule:

> **If the closet is weak, the whole app fails.**

Because of that, the roadmap is intentionally **closet-first**.

Downstream features such as:
- AI stylist
- should-I-buy-or-not
- shop-the-look
- personal lookbook intelligence
- stats and insights
- try-on

must be built on top of a strong closet foundation.

---

## Roadmap principles

### 1. Closet before intelligence
Do not build advanced AI features before the closet lifecycle, metadata quality, and item management flows are strong.

### 2. Foundations before polish
Do not spend time polishing downstream UX while core ingestion, storage, and trust layers are unstable.

### 3. Vertical slices over scattered progress
Build complete, usable slices rather than partially building many domains at once.

### 4. User truth over AI guesses
Any feature that depends on AI output must preserve user control, reviewability, and data provenance.

### 5. Mobile-first, web-supported
The mobile app is the primary product surface.
The web app is a real product surface, but not the main driver of architecture.

---

## Phase order

## Phase 0 -- Monorepo foundation
Create the monorepo structure and root developer workflow.

**Outcome:**
- repo structure exists
- root tooling is wired
- workspace conventions are established

**Why first:**
Everything else depends on a clean working repo.

---

## Phase 1 -- App scaffolds
Create the three main applications:
- mobile
- web
- api

**Outcome:**
- Expo app runs
- Next.js app runs
- FastAPI app runs

**Why now:**
The product needs all three surfaces established early, even if most logic is still missing.

---

## Phase 2 -- Infra and developer experience
Set up local infrastructure, environment handling, migrations, storage, and basic quality tooling.

**Outcome:**
- local database works
- local object storage works
- migrations run
- basic test/lint workflows exist

**Why now:**
The backend cannot evolve safely without stable infra and repeatable local workflows.

---

## Phase 3 -- Auth foundation
Build authentication and user foundation across backend, mobile, and web.

**Outcome:**
- register/login works
- authenticated session flow exists
- protected user scope exists

**Why now:**
Every personal closet, lookbook, recommendation, and try-on flow depends on user identity.

---

## Phase 4 -- Closet schema foundation
Build the core closet data model and lifecycle foundation.

**Outcome:**
- closet item model exists
- lifecycle states exist
- metadata structure exists
- trust/provenance direction is established

**Why now:**
This is the first true product domain and the foundation for everything else.

---

## Phase 5 -- Closet upload and draft flow
Build the first real closet ingestion flow.

**Outcome:**
- user uploads/snaps an item photo
- system creates a draft closet item
- original image is stored

**Why now:**
This is the first real user value in the product.

---

## Phase 6 -- Closet image processing
Add processed item imagery for a clean closet experience.

**Outcome:**
- processed/clean item image pipeline exists
- thumbnails exist
- closet presentation quality improves

**Why now:**
A premium closet experience depends on strong visual presentation.

---

## Phase 7 -- Closet metadata extraction and normalization
Build AI-assisted metadata extraction and normalization into canonical fields.

**Outcome:**
- metadata is extracted
- metadata is normalized
- reviewable field states exist
- low-confidence output is not silently committed

**Why now:**
Search, filtering, similarity, and downstream intelligence depend on structured closet data.

---

## Phase 8 -- Closet confirmation and editing flow
Let users review, edit, and confirm closet items.

**Outcome:**
- user can correct metadata
- item becomes canonical only after review/confirmation
- closet truth is user-controlled

**Why now:**
This completes the trust model of the closet.

---

## Phase 9 -- Closet browse, search, filter, and detail views
Turn closet data into a usable product surface.

**Outcome:**
- closet grid/list works
- item detail works
- filtering/search works
- mobile and web closet usage becomes practical

**Why now:**
The closet must become genuinely usable before downstream features are layered on top.

---

## Phase 10 -- Closet similarity foundation
Add similarity and comparison capabilities on top of confirmed closet data.

**Outcome:**
- duplicate detection foundation exists
- closet comparison logic exists
- similarity explanations exist

**Why now:**
This powers multiple future features and should come only after closet truth is stable.

---

## Phase 11 -- Outfits foundation
Introduce saved outfit composition from closet items.

**Outcome:**
- users can build outfits from owned items
- outfit-item relationships exist

**Why now:**
Outfits are the bridge between the closet and styling/use-history features.

---

## Phase 12 -- Lookbook foundation
Introduce real-world outfit logging.

**Outcome:**
- user can log outfit photos
- lookbook entries exist
- usage history begins to accumulate

**Why now:**
Lookbook data makes the product more personal and enables better insights later.

---

## Phase 13 -- Wear history and insights foundation
Build the analytics layer on top of closet and lookbook behavior.

**Outcome:**
- most worn / least worn logic exists
- stale item detection exists
- category and outfit usage logic exists

**Why now:**
Insights become meaningful only after closet and outfit activity exist.

---

## Phase 14 -- Should-I-buy-or-not
Build candidate item comparison against the closet.

**Outcome:**
- user uploads a candidate item
- system compares it to the closet
- system recommends whether it fits the wardrobe

**Why now:**
This depends on strong metadata, similarity, and closet trust.

---

## Phase 15 -- AI stylist
Build event-aware outfit recommendations and outfit evaluation.

**Outcome:**
- user gets 3 outfit ideas from their closet
- user can upload current outfit photo and get feedback
- improvement suggestions are grounded in owned items

**Why now:**
The stylist becomes much better once the closet, outfits, and usage history are already real.

---

## Phase 16 -- Shop-the-look
Build inspiration-photo shopping and visual matching.

**Outcome:**
- user uploads an inspiration image
- system finds exact or similar purchasable items
- optional purchase reasoning can connect back to the closet

**Why now:**
This feature is stronger once purchase evaluation and similarity foundations already exist.

---

## Phase 17 -- Try-on
Build try-on experiences for:
- owned closet items
- recommended outfits
- candidate purchase items

**Outcome:**
- user can preview how an item or outfit may look on them

**Why now:**
Try-on is valuable, but it should sit on top of a stable core product rather than drive the whole architecture too early.

---

## Phase 18 -- Ranking, polish, and personalization
Improve quality across recommendation-heavy features.

**Outcome:**
- better ranking
- smarter explanations
- better defaults
- stronger UX polish
- improved personalization

**Why last:**
Optimization and polish matter most once the core flows already work.

---

## Dependency logic

The roadmap follows this dependency chain:

**Monorepo -> Apps -> Infra -> Auth -> Closet -> Similarity / Outfits / Lookbook -> Insights -> Buying / Styling / Shopping -> Try-on -> Polish**

If a task conflicts with this order, prefer the earlier dependency unless there is a strong explicit reason not to.

---

## What must be true before downstream features begin

Before heavily building:
- stylist
- should-I-buy-or-not
- shop-the-look
- try-on

the following must already be strong:

- closet item lifecycle
- image upload and storage
- processed closet imagery
- structured metadata
- normalization
- user review/edit flow
- confirmed canonical closet truth
- browse/search/filter usability

If those are weak, downstream features should be delayed.

---

## How plan files should be written

Each detailed phase plan under `plans/phases/` should represent **one coherent phase or vertical slice**.

Good examples:
- `plans/phases/phase-04/phase-04-closet-schema.md`
- `plans/phases/phase-05/phase-05-closet-upload-draft.md`
- `plans/phases/phase-06/phase-06-closet-image-processing.md`

Avoid mixing unrelated slices into one plan.

Bad example:
- one plan that combines closet ingestion, stylist, lookbook, and try-on

Each plan should include:
- goal
- scope
- non-goals
- architecture constraints
- deliverables
- definition of done

---

## Sequencing rule for coding agents

When working with coding agents:

1. read `AGENTS.md`
2. read `ARCHITECTURE.md`
3. read this roadmap
4. read only the current phase plan under `plans/phases/<phase>/`
5. execute one phase at a time

Do not skip ahead to later roadmap phases unless explicitly instructed.

---

## Final roadmap rule

When priorities are unclear, choose the option that:

- strengthens the closet core
- preserves trust in metadata
- improves the actual product foundation
- keeps downstream features grounded in real wardrobe data
- avoids overengineering
