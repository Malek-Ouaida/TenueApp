# AGENTS.md

## Project identity

This project is **Tenue**.

Tenue is an **AI-powered closet companion** centered around a strong personal wardrobe system.
The closet is the foundation of the product. If the closet experience is weak, inaccurate, or unreliable, the rest of the app fails.

This is **not** a social media app.
This is **not** a generic fashion inspiration app.
This is a product that helps users:

- build a usable digital closet
- understand what they own
- get outfit recommendations from their own wardrobe
- decide whether they should buy a new item
- shop visually from inspiration photos
- maintain a personal lookbook
- track outfit and wardrobe statistics
- preview clothing with try-on experiences

The quality bar is:

- startup-grade
- premium consumer UX
- AI-assisted but not AI-dependent
- reliable in core flows
- secure by default
- mobile-first, with web support where appropriate

---

## Product hierarchy

The product priorities are strict.

### Priority 1: Closet
The closet is the core of the entire app.

Without a strong closet, these features become weak or meaningless:
- AI stylist
- should-I-buy-or-not
- shop-the-look similarity and recommendations
- personal lookbook enrichment
- closet stats
- try-on flows using owned items or suggested outfits

The closet must therefore be treated as the highest-priority domain in the product.

### Priority 2: AI features that depend on the closet
Once closet quality is strong, the next most important product features are:
- AI stylist
- should-I-buy-or-not
- shop-the-look
- lookbook intelligence
- stats and insights
- try-on

### Priority 3: polish and expansion
Only after the above is stable should the codebase expand into:
- more advanced styling logic
- richer recommendation systems
- better ranking
- stronger shopping integrations
- additional try-on providers
- advanced personalization

Do not build flashy features on top of a weak closet foundation.

---

## Core product pillars

Unless a task explicitly says otherwise, assume the app is built around these six pillars:

### 1. Closet
The user can:
- add clothing items
- upload one or more photos per item
- edit metadata manually
- browse, search, filter, and sort their wardrobe
- organize by category, subtype, color, material, brand, season, fit, style, occasion, and tags
- distinguish owned items from wishlist / candidate items
- maintain a clean, trustworthy representation of what they actually own

This is the most important feature in the system.

### 2. Shop-the-look
The user uploads a photo of an outfit or clothing item and the system:
- identifies the relevant fashion items in the photo
- searches for exact or similar purchasable items
- ranks options based on similarity, price, and relevance
- helps the user find where to buy them
- can contribute to a buying recommendation when relevant

This feature should support:
- exact-match intent where possible
- similar-item discovery when exact matches are not available
- budget-aware alternatives
- shopping-source recommendations

### 3. AI stylist
The user can:
- specify an event, context, or occasion
- receive 3 outfit suggestions directly from their own closet

The user can also:
- snap or upload a photo of what they are currently wearing
- provide the event or context
- receive a rating or evaluation of the outfit
- receive improvement suggestions
- get recommendations from their own closet for what to pair with the current outfit

The AI stylist should use the closet as the main source of truth whenever possible.

### 4. Should-I-buy-or-not
The user snaps or uploads a picture of an item they are considering buying.

The system compares it against the user’s closet and helps answer:
- does this fit my wardrobe?
- is this redundant?
- does it fill a real gap?
- will I likely wear it?
- should I buy it or not?

This feature must not be a generic opinion generator.
It should be grounded in the actual closet and outfit logic.

### 5. Personal lookbook
The user can upload or snap outfit photos.

Each logged outfit should:
- appear in the user profile / lookbook
- preserve the photo and timestamp
- optionally detect or associate the items worn
- feed usage and analytics systems
- act as part of the user’s history and style memory

The lookbook is not just a gallery.
It is part of the intelligence layer of the app.

### 6. Try-on
The user can preview how something would look on them.

Try-on should support:
- an item from the user’s own closet
- an outfit recommended by the AI stylist
- a candidate item the user is considering buying

The product goal is to help the user visualize how a clothing item or outfit would look on them before styling or purchasing decisions.

Try-on may use external APIs and should be abstracted behind provider interfaces.

---

## Stats and insights

The system should support wardrobe and outfit intelligence such as:

- most worn items
- least worn items
- stale items / not worn recently
- outfit frequency
- category usage
- closet redundancy
- closet gaps

These insights should be grounded in:
- outfit logs
- wear history
- lookbook entries
- closet metadata
- recommendation history where useful

Do not treat stats as decorative.
They are a meaningful product feature.

---

## Explicit non-goals

Do not introduce these unless explicitly requested:

- social feed
- follower system
- public creator profiles
- messaging/chat
- marketplace infrastructure
- full influencer platform features
- custom ML training pipelines for MVP
- microservice sprawl
- overbuilt event-driven infrastructure without product need

Keep the product tightly focused.

---

## Product principles

### 1. Closet first
Any decision that weakens closet quality in order to ship a flashy feature is the wrong decision.

### 2. User truth beats AI guess
AI-generated tags, classifications, matches, or recommendations are advisory.
User-confirmed data is canonical.

### 3. AI must be useful, not decorative
Do not add vague AI experiences.
Each AI feature must solve a concrete user problem.

### 4. The product should feel premium
This is a consumer product and should not feel like an admin dashboard or a demo app.

### 5. Shopping must stay grounded
Shopping-related recommendations should be tied to visual similarity, user wardrobe fit, budget, and usefulness.

### 6. Suggestions must be explainable
For styling and buying features, provide reasoning that is grounded in wardrobe logic, not just a raw score.

### 7. Closet capture is a pipeline, not just CRUD
Adding an item to the closet is a structured pipeline, not a simple record creation flow.

A closet item may move through states such as:
- draft
- processing
- processed
- confirmed
- failed

The product should support:
- original image upload
- processed/clean image generation
- metadata extraction
- metadata normalization
- per-field review/edit
- final confirmation

Do not treat closet ingestion as “upload image and save whatever AI returns.”

### 8. Clean closet presentation matters
The closet should look visually clean and premium.

When available, the system should prefer processed item imagery for closet presentation, such as:
- transparent-background item images
- cleaned item cutouts
- optimized thumbnails for browsing

Original uploads remain important for traceability and recovery, but processed images should usually power the browsing experience.

---

## Engineering principles

### API-first
All core product behavior must be represented in backend services and stable API contracts.
Clients should remain thin.

### Services own business logic
Transport layers are thin.
Business logic lives in services/use-cases.
Persistence lives in repositories/models.

### External providers must be replaceable
Image recognition, shopping search, similarity, background removal, try-on, and AI providers must be wrapped in adapters or provider interfaces.

### End-to-end slices beat isolated scaffolding
Prefer vertical features that actually work over disconnected infrastructure.

### Preserve domain clarity
Closet, lookbook, recommendations, and shopping flows should remain cleanly modeled.
Do not overload one model to handle everything.

### Normalization is a first-class domain concern
AI extraction output must not be treated as final product data.

The system should include a normalization layer responsible for:
- mapping provider output into canonical taxonomies
- resolving aliases and synonym forms
- handling ambiguity
- applying confidence policy
- preserving provenance
- preparing structured metadata for filtering, analytics, and similarity

Do not scatter normalization logic across controllers, UI code, or provider adapters.

### Similarity is a core closet capability
Similarity is not an optional helper feature.
It is a core capability that supports:
- should-I-buy-or-not
- duplicate detection
- closet redundancy detection
- future recommendation quality
- shop-the-look grounding

Implement similarity behind dedicated services and keep it explainable.
Prefer structured overlap and explicit reasoning over black-box scores alone.

---

## Architecture rules

### Backend
- keep route handlers/controllers thin
- no business logic in HTTP handlers
- do not leak ORM models directly to clients
- use explicit request/response schemas
- use clear, structured errors
- prefer paginated list endpoints
- isolate provider integrations behind service boundaries
- long-running image or AI work should use explicit background jobs/tasks when appropriate

### Frontend / mobile / web
- clients should focus on UX, forms, display logic, and orchestration
- do not bury core recommendation or decision logic in the client
- keep API contract usage centralized and typed
- prioritize mobile-first flows and low-friction capture
- premium UX matters in closet creation, outfit logging, and AI flows

### AI flows
Every AI-assisted flow must define:
- input schema
- output schema
- confidence handling where possible
- failure/fallback behavior
- user override/edit path
- what gets stored versus what stays ephemeral

Do not rely on prompts alone for product logic that should exist in code.

---

## Preferred domain concepts

Use these concepts consistently where relevant:

- **ClosetItem**: a clothing or accessory item the user owns
- **ClosetItemImage**: an image associated with a closet item
- **ClosetItemMetadata**: normalized attributes such as category, color, material, fit, season, occasion, style
- **Outfit**: a composed outfit, usually built from closet items
- **LookbookEntry**: a real-world logged outfit photo and its associated data
- **WearLog**: a timestamped record of an item or outfit being worn
- **CandidateItem**: an item the user is considering buying
- **PurchaseEvaluation**: a should-I-buy-or-not result grounded in closet comparison
- **ShopTheLookResult**: visual match / similar-item shopping results
- **StylistRecommendation**: an outfit recommendation from the AI stylist
- **OutfitEvaluation**: a rating and improvement result for a user’s current outfit
- **Insight**: a stats or analytics output
- **ProviderResult**: raw or semi-processed data returned by an external provider

Avoid collapsing these into a single overloaded entity.

---

## Data modeling guidance

The data model should make it easy to support:
- strong closet CRUD
- multiple images per item
- user-edited metadata
- AI-extracted metadata
- outfit composition
- lookbook entries with photos
- wear history
- candidate purchase evaluation
- visual shopping results
- analytics and history
- future try-on outputs

Important rules:
- user-authored data and AI-derived data should be distinguishable
- normalized fields should exist for filtering, querying, and stats
- raw provider outputs may be stored where traceability is useful
- stats should be derivable without rebuilding the system
- design for future extensibility, but do not overbuild

---

## Security and privacy rules

This app handles personal images, body-related imagery, wardrobe data, and potentially sensitive preference patterns.

Always:
- validate uploads strictly
- enforce file size/type limits
- sanitize and validate user input
- avoid trusting provider output blindly
- keep auth boundaries clean
- protect private media appropriately
- avoid leaking raw provider details to clients
- log carefully and minimally

Never:
- hardcode secrets
- commit credentials
- expose stack traces to clients
- trust client-supplied ownership claims
- make personal outfit or closet media public by default

### AI trust and provenance rules
The system must preserve where important metadata came from.

For important closet fields, the product should be able to distinguish:
- AI-suggested values
- user-entered values
- AI values later edited by the user
- values that still need review

Never silently convert ambiguous or low-confidence AI output into canonical closet truth.
Review-required values must remain reviewable.

---

## Performance rules

Optimize the experience for these high-priority flows:
- adding closet items
- uploading item images
- browsing/searching/filtering closet items
- generating outfit suggestions
- evaluating whether to buy an item
- logging a lookbook outfit
- computing wardrobe insights
- processing try-on requests

Prefer:
- paginated and efficient list endpoints
- async/background processing for slow provider calls
- cached derived results where appropriate
- responsive image pipelines
- fast perceived UX in capture and recommendation flows

Do not prematurely optimize low-value flows.

---

## Workflow rules for agents

Before changing code:
1. inspect the repository structure
2. inspect existing patterns and conventions
3. inspect scripts, manifests, configs, and env assumptions
4. inspect relevant models, schemas, services, routes, and UI modules
5. understand the current feature slice before editing

When implementing:
1. make the smallest coherent set of changes that fully solves the task
2. preserve architecture boundaries
3. keep naming aligned with existing domain concepts
4. update schemas, types, and tests together
5. choose explicit and maintainable solutions

When working on closet features:
1. preserve the item lifecycle and valid state transitions
2. preserve the separation between raw provider output, normalized metadata, and confirmed user truth
3. do not bypass review paths just to simplify implementation
4. keep provider integrations mockable for local development and tests
5. preserve explainability for similarity and purchase-evaluation behaviors

Before finishing:
1. run relevant tests
2. run lint/format/typecheck where available
3. verify imports/build integrity
4. verify backend/client contract alignment
5. clearly state assumptions and limitations

Do not claim completion without verification when verification is available.

---

## Testing expectations

Every meaningful change should be validated at the appropriate level.

Prefer:
- unit tests for service/domain logic
- integration tests for API and persistence behavior
- focused UI tests for critical flows
- smoke tests for end-to-end product-critical scenarios

High-priority flows that must remain stable:
- authentication
- closet item creation/editing/deletion
- closet image upload
- metadata extraction
- outfit generation
- outfit evaluation
- should-I-buy-or-not
- lookbook logging
- stats/insights generation
- try-on request flow

When fixing a bug, add or update a test where practical.

---

## Definition of done

A task is done only when:
- the requested behavior works end-to-end
- the implementation respects architecture boundaries
- validation and error handling exist
- tests were added or updated where appropriate
- the code is readable and maintainable
- the change does not weaken the closet core
- no obvious product-breaking edge case was ignored
- no unnecessary complexity was introduced

---

## UX expectations

This is a premium consumer-facing product.

The UX should feel:
- clean
- modern
- stylish
- minimal
- fast
- mobile-first
- polished

Prioritize:
- strong visual hierarchy
- high-quality empty states
- smooth image-driven flows
- clear loading and error states
- low-friction logging and capture
- simple but confident AI interactions

Avoid:
- clutter
- admin-panel feeling
- noisy layouts
- vague AI messaging
- too many taps
- complicated forms where image-first flows are better

---

## AI product rules

For every AI feature, define:
- the exact user problem
- the exact input
- the exact output
- the fallback behavior
- the edit/override path
- what data gets stored
- how confidence or uncertainty is handled

Do not ship vague AI magic.
Ship useful product behavior.

---

## Suggested implementation order

Unless explicitly told otherwise, build in this order:

1. authentication and user foundation
2. closet item model and CRUD
3. closet image upload/storage
4. metadata extraction and manual correction flows
5. closet browse/search/filter/sort
6. outfit model and composition
7. AI stylist from closet
8. candidate item ingestion for should-I-buy-or-not
9. closet comparison and purchase evaluation
10. shop-the-look search and shopping results
11. lookbook logging and item recognition from outfit photos
12. stats and insights
13. try-on integration and polish

Do not jump to try-on before the closet, recommendation, and item flows are stable.

---

## Repo guidance

Assume the repo may include:
- backend
- web
- mobile
- shared packages
- infra/config

Use the existing structure.
Do not reorganize the whole repo unless explicitly asked.

If commands or conventions already exist, use them.
Do not invent new conventions unnecessarily.

Treat mobile as a first-class surface if present.
Do not add large new scaffolding unless the task requires it.

---

## Communication style for agent outputs

When reporting completed work:
- state what changed
- state what was verified
- state assumptions
- state limitations or follow-up risks

Be concise and honest.
Do not overclaim readiness.

---

## What to avoid

Avoid:
- weakening closet quality to accelerate flashy features
- mixing transport, business, and persistence logic
- leaking vendor-specific details across the codebase
- giant files with mixed responsibilities
- fake implementations presented as complete
- schema drift between backend and clients
- recommendation logic with no grounding in the closet
- AI outputs being committed as canonical closet truth without clear review, provenance, or user control
- broad rewrites for narrow tasks

---

## Preferred mindset

Act like a pragmatic founding engineer building a premium consumer product.

Protect:
- the closet core
- product focus
- delivery speed
- code quality
- replaceable integrations
- future extensibility

Choose the simplest robust solution that strengthens the foundation of the app.
For closet-related work, prefer solutions that strengthen lifecycle integrity.
