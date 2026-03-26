# ARCHITECTURE.md

## Overview

Tenue is an AI-powered closet companion built around one core rule:

> The closet is the center of the system.
> If the closet is weak, all downstream intelligence becomes weak.

This architecture exists to support a premium, image-heavy consumer product where users can:
- build a clean and trustworthy digital closet
- get AI-powered outfit recommendations from their own wardrobe
- evaluate whether a new item fits their wardrobe
- shop visually from inspiration photos
- maintain a personal lookbook
- generate wardrobe stats and insights
- preview items or outfits through try-on flows

The architecture is intentionally designed so that every major feature either:
- creates closet data
- improves closet data
- compares against closet data
- reads closet data
- derives recommendations or insights from closet data

---

## Architectural goals

The system should optimize for:

1. **Closet-first reliability**
2. **Premium image-first product behavior**
3. **Strong domain boundaries**
4. **Replaceable external providers**
5. **AI-assisted but user-controlled workflows**
6. **Clear API contracts**
7. **Fast iteration without architectural chaos**

The system should **not** optimize for:
- premature microservices
- overengineered infrastructure
- custom ML training pipelines for MVP
- abstract complexity with no product value
- flashy downstream features before the closet foundation is stable

---

## Architecture style

Tenue should be built as a **modular monolith**.

For MVP and early growth, the correct shape is:
- one backend application
- clearly separated product domains
- strict layering
- provider integrations behind interfaces
- optional async/background execution for slow workflows

This should remain a modular monolith until there is a real operational reason to split services.

### Recommended system shape

- **apps/api**
  - API transport layer
  - domain modules
  - service/use-case layer
  - repository/data-access layer
  - provider adapters
  - normalization and similarity logic
  - background processing hooks
- **apps/web**
- **apps/mobile**
- **packages/shared** where useful
- **infra/** for local/dev infrastructure and deployment configuration

---

## Core architectural principles

### 1. Closet-centered design
The closet is the primary product domain.
Other domains depend on closet quality.
The closet should not be compromised to accelerate flashy downstream features.

### 2. Thin transport layer
Routes/controllers are transport only.
They may:
- validate request shape
- resolve auth/user scope
- call services
- map responses/errors

They must not contain business logic.

### 3. Services own product behavior
Use-case logic belongs in services.
Examples:
- create closet item draft
- process closet item image
- normalize extracted metadata
- confirm closet item
- generate outfit suggestions
- evaluate candidate purchase
- compute wardrobe insights

### 4. Persistence is not business logic
Repositories and ORM models handle storage and retrieval.
They do not decide:
- recommendation logic
- confirmation policy
- trust policy
- similarity logic
- provider fallback behavior

### 5. Providers must be replaceable
All third-party capabilities must be wrapped behind provider interfaces.
This includes:
- background removal
- garment analysis
- metadata extraction
- embeddings
- visual search
- shopping retrieval
- try-on
- LLM-based recommendation/evaluation

No vendor-specific assumptions should leak through the codebase.

### 6. User-confirmed data is canonical
AI may suggest.
The user decides what becomes truth.

### 7. Build vertical slices
Prefer end-to-end working product slices over disconnected scaffolding.

### 8. Preserve explainability
For recommendation, purchase evaluation, and similarity features, explanations matter.
The system should not devolve into opaque black-box outputs.

---

## Domain map

The system should be organized into these domains.

### 1. `auth`
Responsible for:
- users
- authentication
- sessions/tokens
- authorization boundaries

This domain must stay separate from product logic.

---

### 2. `closet`
This is the most important domain in the system.

Responsible for:
- closet item lifecycle
- item creation and editing
- original and processed item images
- normalized metadata
- user-confirmed metadata
- filtering/search/sort support
- item ownership state
- closet presentation quality

This domain is the upstream dependency for:
- stylist
- purchase evaluation
- shop-the-look grounding
- lookbook enrichment
- insights
- try-on with owned items

---

### 3. `outfits`
Responsible for:
- outfit composition
- saved outfit combinations
- outfit-item relationships
- reusable outfit records

Outfits are not closet items.
They are combinations of closet items.

---

### 4. `lookbook`
Responsible for:
- logging real-world outfit photos
- timestamped outfit history
- optional item association from logged looks
- usage/wear enrichment
- style memory over time

Lookbook entries are not just media.
They are an input into statistics, personalization, and closet intelligence.

---

### 5. `stylist`
Responsible for:
- generating 3 outfit suggestions from the user's closet
- event/occasion-aware styling
- evaluating a user's current outfit photo
- suggesting improvements based on the closet
- recommending what to pair with what the user is currently wearing

This domain reads from:
- closet
- outfits
- lookbook
- context such as occasion, weather, or style goal

It does not own canonical closet truth.

---

### 6. `purchase_evaluation`
Responsible for:
- candidate item ingestion
- closet comparison
- redundancy detection
- wardrobe fit evaluation
- gap-filling logic
- should-I-buy-or-not recommendation

This is the domain behind:
- "does this fit my wardrobe?"
- "is this redundant?"
- "will I actually wear this?"
- "should I buy this or not?"

It must be grounded in the actual closet, not generic taste advice.

---

### 7. `shop_the_look`
Responsible for:
- parsing inspiration photos
- identifying relevant clothing targets in an image
- finding exact or similar purchasable items
- budget-aware alternative discovery
- surfacing where to buy

This domain is shopping-oriented.
It may collaborate with `purchase_evaluation`, but it should not absorb wardrobe-fit logic by default.

---

### 8. `insights`
Responsible for:
- most worn items
- least worn items
- stale items / not worn recently
- outfit frequency
- category usage
- closet redundancy
- closet gaps
- wardrobe summaries

This domain reads from:
- closet
- outfits
- lookbook
- wear history
- recommendation history when useful

---

### 9. `try_on`
Responsible for:
- try-on request orchestration
- provider integration for visualization
- using:
  - owned closet items
  - AI-stylist outfit ideas
  - candidate purchase items

This domain must remain provider-agnostic.

---

### 10. `provider_adapters`
Responsible for:
- external API integrations
- request/response translation
- provider-specific retries/timeouts
- provider capability boundaries

This is an infrastructure-supporting domain, not a product domain.

---

## Dependency direction

Use this dependency direction:

- `auth` is foundational and separate
- `closet` is the central product domain
- `outfits`, `lookbook`, `stylist`, `purchase_evaluation`, `insights`, and `try_on` may depend on `closet`
- `shop_the_look` may collaborate with `purchase_evaluation`
- product domains may depend on provider interfaces/adapters
- provider adapters must not depend on product domains

Mental model:
- **closet is upstream**
- **intelligence/recommendation domains are downstream**
- **providers are pluggable infrastructure**

---

## Closet architecture

### Closet as a staged pipeline
Closet ingestion is not a simple "upload image and save record" flow.

It is a staged capture pipeline designed to produce:
- a clean visual result
- structured metadata
- trustworthy field state
- reviewable AI suggestions
- a confirmed canonical item

A closet item may move through lifecycle states such as:
- `draft`
- `processing`
- `processed`
- `confirmed`
- `failed`

These states are part of the product architecture, not just implementation detail.

### Closet image model
Each closet item should support:
- original uploaded image
- processed or cleaned image
- thumbnail image

The original image is preserved for traceability and retry safety.
The processed image should usually be preferred for closet display when available so the closet looks clean and premium.

### Closet metadata model
Closet metadata should support:
- normalized canonical fields
- user-edited fields
- AI-suggested fields
- confidence/provenance state
- review-required candidates when ambiguity exists

Closet data must be strong enough to support:
- browse/filter/search
- purchase evaluation
- stylist recommendations
- similarity
- insights
- future personalization

---

## Core closet ingestion flow

### Flow: add item to closet
1. user snaps or uploads an image
2. backend stores the original image
3. system creates a draft closet item
4. processing pipeline runs
5. processed/clean item image and thumbnail are generated when possible
6. garment/image analysis extracts structured metadata
7. normalization maps provider output into canonical taxonomies
8. field-level confidence and provenance are preserved
9. item becomes `processed` or `failed`
10. user reviews/edits important metadata
11. item becomes `confirmed`

Important rule:
A closet item should not silently become canonical based only on AI output.

---

## Trust model and source-of-truth rules

### Product trust rule
The system must follow this rule:

> No silent forced guesses.

Ambiguous or low-confidence values should remain reviewable rather than being silently committed as truth.

### Canonical truth
Canonical truth should be:
- user-entered data
- user-confirmed AI suggestions
- user-edited values

### Advisory truth
AI output is advisory.
It may include:
- category suggestions
- color suggestions
- material suggestions
- similarity signals
- styling suggestions
- shopping matches
- buy/don't-buy reasoning

But it is not canonical by default.

### Provenance requirements
For important fields, the system should be able to distinguish:
- AI suggestion
- user-provided value
- AI value later edited by the user
- value still needing review

This trust layer is an architectural concern, not just a UI nicety.

---

## Normalization architecture

Normalization must be treated as a **first-class domain concern**.

It should be responsible for:
- mapping provider output into canonical taxonomies
- alias handling
- ambiguity handling
- confidence handling
- provenance mapping
- preparing structured data for filtering, similarity, and analytics

Normalization logic must not be scattered across:
- route handlers
- UI code
- random helper files
- provider adapters

Provider adapters return provider-shaped output.
Normalization converts that output into product-shaped truth candidates.

---

## Similarity architecture

Similarity is a core closet capability.

It supports:
- should-I-buy-or-not
- duplicate detection
- closet redundancy detection
- future recommendation quality
- shop-the-look grounding

Similarity should use a hybrid model such as:
- normalized attribute overlap
- semantic similarity
- visual similarity where available
- explicit reasons/explanations

Important rules:
- similarity must remain explainable
- fallback behavior must exist if one signal is missing
- the system should not depend on a single black-box score

Similarity should live behind dedicated services, not be spread through unrelated domains.

---

## Product flows

### Flow 1: AI stylist
1. user gives an event or context
2. stylist reads confirmed closet data
3. stylist produces 3 outfit suggestions
4. results include reasoning
5. user may save, modify, or ignore them

#### Outfit evaluation mode
1. user uploads a current outfit photo
2. user provides event/context
3. system evaluates the outfit
4. system suggests improvements grounded in the user's own closet
5. user can use suggestions directly

Important rule:
The stylist should prefer the user's closet over external inspiration whenever possible.

---

### Flow 2: Should-I-buy-or-not
1. user uploads candidate item image
2. system extracts candidate metadata
3. system compares candidate against confirmed closet items
4. system evaluates:
   - compatibility
   - redundancy
   - versatility
   - wardrobe gap-filling
5. result returns a recommendation and reasoning

Important rule:
This is not a generic fashion-opinion feature.
It must be grounded in the actual wardrobe.

---

### Flow 3: Shop-the-look
1. user uploads inspiration image
2. system identifies relevant target items
3. system retrieves exact or similar shopping results
4. optional budget-aware ranking occurs
5. selected results may be passed to purchase evaluation against the closet

Important rule:
Shopping retrieval and closet fit evaluation are related but separate concerns.

---

### Flow 4: Lookbook logging
1. user uploads or snaps an outfit photo
2. system creates a lookbook entry
3. system may detect or associate worn items
4. wear history is updated where appropriate
5. insights and stylist systems may use this data later

Important rule:
Lookbook entries should enrich wardrobe intelligence rather than remain isolated media records.

---

### Flow 5: Try-on
1. user chooses an owned item, suggested outfit, or candidate item
2. system prepares a try-on request
3. provider adapter generates or retrieves try-on result
4. result is stored or returned according to product rules
5. client displays the result

Important rule:
Try-on providers must remain replaceable.

---

## Canonical data concepts

The exact schema may evolve, but these concepts should remain distinct.

### Core entities
- `User`
- `ClosetItem`
- `ClosetItemImage`
- `ClosetItemFieldState`
- `Outfit`
- `OutfitItem`
- `LookbookEntry`
- `WearLog`
- `CandidateItem`
- `PurchaseEvaluation`
- `ShopTheLookQuery`
- `ShopTheLookResult`
- `StylistRecommendation`
- `OutfitEvaluation`
- `Insight`
- `TryOnRequest`
- `TryOnResult`
- `ProviderResult`
- `ProcessingRun`

### Modeling rules
- closet items and candidate purchase items should remain distinct concepts
- raw provider output and normalized product data should remain distinguishable
- user-authored and AI-derived values should remain distinguishable
- wear history should be modelable independently from saved outfits
- normalized fields should exist for filtering, analytics, and recommendation logic

---

## Layered backend structure

Recommended intent:

```text
apps/api/
  app/
    api/
      routes/
      schemas/
    domains/
      auth/
      closet/
        services/
        repositories/
        providers/
        normalization/
        similarity/
      outfits/
      lookbook/
      stylist/
      purchase_evaluation/
      shop_the_look/
      insights/
      try_on/
    core/
      config/
      security/
      database/
      storage/
      logging/
    background/
      jobs/
      orchestration/
```

The intent matters more than exact naming:

- `api` = transport and schema boundary
- `domains` = product logic
- `repositories/models` = persistence
- `providers` = external integrations
- `normalization/similarity` = closet-native internal capabilities
- `core` = shared infrastructure
- `background` = slow or retryable workflows

---

## API design rules

### General rules
- use explicit request/response schemas
- do not leak raw ORM models
- prefer stable DTOs
- use structured errors
- paginate list endpoints
- keep naming consistent across backend and clients

### Endpoint style

Use:

- resource-oriented endpoints for CRUD
- explicit action endpoints for use-cases

Examples:

- closet item CRUD = resource endpoints
- process closet item = action endpoint
- confirm closet item = action endpoint
- evaluate purchase = action endpoint
- generate stylist suggestions = action endpoint
- run try-on = action endpoint

### Contract ownership

Backend contracts are owned by the backend.
Clients should follow the backend contract, not invent parallel ones.

---

## Background processing guidance

Some flows are naturally slow or failure-prone and may require async/background execution:

- image cleanup/background removal
- metadata extraction
- embeddings or similarity enrichment
- shop-the-look retrieval
- try-on generation
- heavy insight recomputation

Use explicit background orchestration when:

- provider latency is variable
- retries are needed
- the operation is expensive
- the UX benefits from staged progress

Do not introduce queue complexity for flows that are fast enough synchronously.

---

## Media and storage architecture

This is an image-heavy product.
Media is first-class.

Support media categories such as:

- closet item images
- processed closet cutouts
- closet thumbnails
- lookbook outfit photos
- candidate purchase images
- inspiration images
- try-on outputs

Rules:

- validate uploads strictly
- keep original uploads for traceability
- prefer processed media for closet presentation
- store private media securely
- use controlled/signed access where appropriate
- avoid making user fashion/body imagery public by default

---

## Search, browse, and filtering model

Closet browsing must feel strong and fast.

The system should support structured filtering and search over:

- category
- subtype
- color
- material
- pattern
- season
- occasion
- brand
- style tags
- favorites / archived state
- wear recency / frequency
- owned vs candidate/wishlist state where relevant

This is why normalized metadata matters.
The closet must not be treated as a blob of freeform text.

---

## Recommendation architecture

Recommendation should be hybrid rather than magical.

Use a combination of:

- normalized wardrobe metadata
- deterministic product rules
- similarity services
- explicit compatibility logic
- AI reasoning where useful
- explanation generation

Important rule:
Do not bury the whole recommendation system inside prompts.

Product logic that usually belongs in code:

- duplicate detection
- closet overlap detection
- stale item thresholds
- wear frequency calculations
- gap detection
- compatibility constraints
- confidence policy
- review-required logic

AI can enrich.
Code should still govern core product behavior.

---

## Provider abstraction pattern

Every provider integration should live behind a clear interface.

Examples:

- `BackgroundRemovalProvider`
- `GarmentAnalysisProvider`
- `EmbeddingProvider`
- `VisualSearchProvider`
- `ShoppingSearchProvider`
- `TryOnProvider`
- `StylistProvider`

Each provider boundary should define:

- input contract
- output contract
- failure modes
- retry assumptions
- cost/performance concerns when useful

Provider-specific response parsing should never be duplicated across multiple product domains.

### Mockability

Provider interfaces should support mock implementations for:

- local development
- tests
- cost control
- deterministic debugging

---

## Client architecture guidance

### Web and mobile are product surfaces, not business-logic owners

Clients should own:

- UX flow orchestration
- forms
- loading/error states
- display logic
- local interaction polish
- image capture/presentation flows

Clients should not own:

- canonical recommendation logic
- normalization logic
- purchase-evaluation rules
- trust policy
- duplicate logic

### Shared concerns

If both web and mobile exist, centralize where sensible:

- API client contracts
- shared domain vocabulary
- design tokens and UI patterns when appropriate
- shared request/response typing where practical

---

## Observability and safety

Because the product handles personal images and style-related user data:

- log carefully
- avoid logging raw sensitive media payloads unless necessary
- avoid logging tokens or secrets
- use structured logs
- capture provider failures clearly
- capture processing state transitions clearly
- surface safe user-facing errors
- keep internal provider details out of user-facing API responses

---

## Scaling guidance

This architecture should scale by:

- adding domains, not rewriting foundations
- adding provider adapters behind interfaces
- improving normalization and similarity incrementally
- increasing async processing only when justified
- improving caching/indexing when usage demands it

Do not split services early.
A clean modular monolith is the preferred shape for MVP and early scale.

---

## Anti-patterns to avoid

Avoid:

- putting business logic in controllers
- mixing provider logic directly into product domains
- silently converting uncertain AI output into canonical closet truth
- collapsing closet items, outfits, and candidate items into one overloaded model
- building try-on before the closet foundation is strong
- treating lookbook as just an image gallery with no intelligence value
- storing only freeform text where normalized metadata is required
- broad rewrites for narrow tasks
- client/backend schema drift
- recommendation logic with no grounding in the closet

---

## Recommended implementation order

Unless a task explicitly says otherwise, use this build order:

1. auth foundation
2. closet item lifecycle and CRUD
3. image upload/storage
4. image processing and cleaned closet presentation
5. metadata extraction
6. normalization and trust layer
7. confirmation/edit flow
8. outfit composition
9. lookbook logging
10. wear-history and insight foundations
11. AI stylist
12. should-I-buy-or-not
13. shop-the-look
14. try-on
15. ranking/personalization polish

This order exists because every downstream feature becomes better once the closet, trust model, and wear-history foundation are strong.

---

## Final architectural rule

When a design choice is unclear, prefer the option that:

- strengthens the closet core
- preserves lifecycle integrity
- preserves normalization and provenance
- keeps providers replaceable
- maintains user control over AI output
- keeps recommendation behavior explainable
- supports a premium image-first consumer experience
- avoids overengineering
