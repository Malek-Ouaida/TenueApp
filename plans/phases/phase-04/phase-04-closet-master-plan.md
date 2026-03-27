0. What this product is now

Tenue is no longer a social fashion app.

It is now a closet companion built around one core promise:

turn messy clothing photos into a trustworthy digital wardrobe that powers review, search, style help, duplicate detection, and later “should I buy this?”, outfit intelligence, and try-on flows.

The closet is the foundation.
If the closet data is bad, every later feature becomes fake, noisy, or unusable.
So the plan is to build the closet as a trust-aware system, not just an image upload feature.

1. Core product goal

A user should be able to:

take or upload a clothing photo
let the system process it
get AI-generated metadata suggestions
review and edit those suggestions
confirm the item into their closet
browse, search, and filter their closet
detect duplicates or very similar items
later use this clean closet for styling, shopping decisions, stats, and try-on

That is the whole mission of the closet phase.

2. MVP philosophy

This closet MVP must optimize for:

reliability over magic
cheap/free-first providers
manual fallback at every step
clear user trust
mobile-first UX
clean backend contracts
future extensibility

This means:

AI can suggest, but never silently become truth
every item enters through a review layer
the user can always finish the item manually
expensive services are avoided unless truly necessary
embeddings are not on the critical path
the taxonomy stays small and versioned
3. What “done” means for the closet phase

The closet foundation is done when an authenticated user can:

create a closet draft
upload a garment image securely
trigger async processing
get a usable processed image or safe fallback original
receive extracted clothing metadata
review confidence-aware suggestions
edit or correct fields
confirm the item into the closet
browse confirmed items
search and filter the closet
open an item detail page
inspect similar/duplicate candidates
retry failures without losing the item

4. What is in scope vs not in scope
In scope
closet draft lifecycle
secure upload flow
private image storage
image preprocessing
background removal
raw metadata extraction
normalization
trust/provenance layer
confirmation + editing
closet browse/search/filter/detail
duplicate/similarity detection
audit/history
retry and resumability
Not in scope for this phase
social posting
feeds
public profiles
cross-user recommendations
automatic closet merges
advanced outfit generation
full “should I buy this?” decision engine
virtual try-on implementation itself
perfect brand/logo detection
giant fashion ontology

Those later features will consume the closet foundation.

5. Product principles that must not be broken
5.1 AI is assistive, not authoritative

The user owns the truth.
AI only proposes candidates.

5.2 Review before closet

Items should not go straight into the “real closet.”
They first go into a Needs Review flow.

5.3 Manual completion must always work

If background removal fails, extraction fails, normalization fails, or providers timeout, the user must still be able to complete the item manually.

5.4 Confirmed data powers downstream features

Search, styling, duplicate detection, stats, and later shopping logic should use confirmed metadata by default.

5.5 MVP taxonomy must stay small

Do not build a huge fashion database in v1.

5.6 Explainability matters

Duplicate/similarity results should show why two items look related.

5.7 Minimal state complexity

Do not create five overlapping workflow machines. Keep the model lean.

6. Recommended stack
Backend
FastAPI
Pydantic v2
SQLAlchemy 2.x
Alembic
Database
Supabase Postgres
Storage
Supabase Storage or S3-compatible abstraction
Worker model
separate worker process
durable job tables in Postgres
no fragile in-request background jobs
Image processing
in-house with:
Pillow
OpenCV where needed
libvips optional later
External providers for MVP
Background removal
Primary: Photoroom
Backup: remove.bg
Metadata extraction
Primary: Gemini 2.5 Flash-Lite
Backup: OpenAI GPT-5 mini
Brand/logo detection
skip dedicated provider in MVP v1
Similarity
no paid embeddings in MVP v1
use:
perceptual hash
normalized metadata overlap
explainable scoring

This is the cheapest smart stack for the MVP.

7. Closet user flow
Flow A — Add an item
User taps add item
Draft item is created
User uploads photo
Upload is finalized
Item enters processing queue
Image is cleaned / background removed / thumbnails generated
Metadata is extracted
Metadata is normalized
Item appears in Needs Review
User edits / confirms
Item moves into Confirmed Closet
Flow B — Failure handling

If any AI step fails:

keep original photo
preserve draft item
mark failed step clearly
allow manual entry
allow retry
Flow C — Duplicate awareness

After confirmation:

compute similarity signals
surface “possible duplicates” or “similar items”
let user dismiss or mark duplicate
do not auto-merge in MVP
8. Minimal lifecycle design

Keep it simple.

Item lifecycle status
draft
processing
review
confirmed
archived
Processing status
pending
running
completed
completed_with_issues
failed
Review status
needs_review
ready_to_confirm
confirmed

That is enough.
Do not overcomplicate this with too many overlapping enums.

9. Core data model
closet_items

Main item record.

Suggested fields:

id
user_id
lifecycle_status
processing_status
review_status
primary_image_id
title
failure_summary
confirmed_at
timestamps
media_assets

Object-store-backed asset records.

Fields:

id
user_id
bucket
key
mime_type
file_size
checksum
width
height
source_kind
is_private
timestamps
closet_item_images

Links items to assets with roles.

Roles:

original
processed
thumbnail
mask
reference
processing_runs

One record per processing/extraction pipeline attempt.

Fields:

id
closet_item_id
run_type
status
retry_count
started_at
completed_at
failure_code
failure_payload
provider_results

Append-only raw provider responses.

Fields:

id
closet_item_id
processing_run_id
provider_name
provider_model
provider_version
task_type
raw_payload
status
timestamps
closet_item_field_candidates

Raw candidate values proposed by AI.

Fields:

id
closet_item_id
field_name
raw_value
normalized_candidate
confidence
provider_result_id
applicability_state
conflict notes
timestamps
closet_item_field_states

Current trust-aware value per field.

Fields:

id
closet_item_id
field_name
canonical_value
source
confidence
review_state
applicability_state
taxonomy_version
timestamps

review_state:

pending_user
user_confirmed
user_edited
system_unset

applicability_state:

value
unknown
not_applicable
closet_item_metadata_projection

Flattened queryable metadata record for search/filter/detail.

closet_item_audit_events

Immutable audit history.

closet_item_similarity_edges

Explainable similarity relationships.

Fields:

id
item_a_id
item_b_id
similarity_type
score
signals_json
decision_status
timestamps
10. MVP taxonomy v1

Keep it intentionally narrow.

Primary categories
tops
bottoms
dresses
outerwear
shoes
bags
accessories
Example subcategories
Tops
t-shirt
shirt
blouse
tank top
sweater
hoodie
Bottoms
jeans
trousers
shorts
skirt
leggings
Dresses
mini dress
midi dress
maxi dress
Outerwear
jacket
coat
blazer
cardigan
Shoes
sneakers
boots
heels
flats
sandals
loafers
Bags
tote
shoulder bag
crossbody
backpack
clutch
Accessories
belt
hat
scarf
sunglasses
jewelry
Colors

Start with a controlled list:

black
white
gray
beige
brown
blue
navy
green
red
pink
purple
yellow
orange
silver
gold
multicolor
Materials
cotton
denim
wool
leather
faux leather
linen
silk
satin
knit
polyester
suede
chiffon
Patterns
solid
striped
plaid
floral
animal print
polka dot
graphic
textured
Optional style/occasion tags

Keep tiny in MVP:

casual
formal
business
evening
sporty
summer
winter

Version this taxonomy from day one.

11. Required item fields for confirmation

To keep confirmation friction low, require only:

at least one active image
primary category
subcategory

Everything else can remain:

suggested
edited
unknown
not applicable

This is critical for keeping the flow usable.

12. AI and trust architecture
Stage 1 — Image processing

Goal: produce a clean usable image.

Tasks:

decode image safely
normalize orientation
generate thumbnail
remove background if possible
preserve fallback original if not
Stage 2 — Raw extraction

Goal: get structured metadata suggestions.

Examples:

category
subcategory
color
material
pattern
fit
sleeve length
neckline
hem length
brand hint
seasonality
style tag
Stage 3 — Normalization

Goal: map raw outputs into controlled vocabulary.

Examples:

“tee”, “tee shirt” -> t-shirt
“navy blue” -> navy
“fake leather” -> faux leather
Stage 4 — Trust materialization

Goal: decide field state without claiming truth.

Each field becomes:

current canonical value
source
confidence
review state
applicability state
Stage 5 — Human confirmation

The user:

accepts
edits
clears
marks not applicable
confirms item

No AI value should quietly become closet truth without user involvement.

13. API design principles
Rules
routers stay HTTP-only
services contain business logic
models are persistence-only
clients stay thin
cursor pagination everywhere relevant
deterministic errors everywhere
idempotency for all critical mutation flows
Core endpoints
Draft/upload
POST /closet/drafts
GET /closet/drafts/{id}
POST /closet/drafts/{id}/upload-intents
POST /closet/drafts/{id}/uploads/complete
Review and processing
GET /closet/review
GET /closet/items/{id}/processing
POST /closet/items/{id}/reprocess
GET /closet/items/{id}/extraction
POST /closet/items/{id}/reextract
Confirmation/editing
GET /closet/items/{id}/review
PATCH /closet/items/{id}
POST /closet/items/{id}/confirm
POST /closet/items/{id}/retry
Browse/detail
GET /closet/items
GET /closet/items/{id}
GET /closet/items/{id}/history
Similarity
GET /closet/items/{id}/similar
GET /closet/items/{id}/duplicates
POST /closet/similarity/{edge_id}/dismiss
POST /closet/similarity/{edge_id}/mark-duplicate
Metadata options
GET /closet/metadata/options
14. Background job design

Required jobs:

upload validation
asset promotion
image preprocessing
background removal
thumbnail generation
metadata extraction
normalization/projection rebuild
similarity recomputation
retry jobs
Job rules
durable queue in Postgres
resumable from failed step
retry only retryable failures
capped exponential backoff
manual retry for user-fixable failures
provider calls isolated behind adapters
observability for latency, failures, retry count, queue depth
15. Similarity strategy for MVP

Do not make embeddings required in v1.

Use:
perceptual hash
normalized category/subcategory match
color overlap
material overlap
pattern overlap
optional title/brand overlap
simple weighted explainable score
Example signals
same category: +high
same subcategory: +high
near-identical image hash: +very high
same color + material: +medium
conflicting category: strong penalty
Output

Return:

score
label (possible duplicate, similar item)
signal breakdown

No black-box mysterious score.
No auto-merging.

16. Security and reliability requirements
Upload safety
signed upload intents
MIME allowlist
file size cap
dimension cap
checksum verification
decode validation
quarantine/staging prefix before finalize
Access control
user-owned items only
private storage by default
signed short-lived download URLs
never expose raw storage internals
Abuse control
upload rate limits
retry caps
provider concurrency caps
duplicate finalize suppression
idempotency keys
Consistency
state transitions must go through services
important writes must be atomic
audit trail for all important actions
Safe degradation
cutout fails -> keep original
extraction fails -> manual entry
normalization weak -> keep low-confidence state
similarity unavailable -> item still works normally

17. Phase implementation plan — 8 sprints
Sprint 1 — Closet schema and lifecycle
Goal

Build the domain foundation correctly before touching providers.

Deliver
closet tables
lifecycle/status model
taxonomy versioning
repositories/services structure
worker skeleton
error catalog
metadata options endpoint
Acceptance
migrations run cleanly
state transitions are enforced
closet domain boundaries are clear
taxonomy contract exists
worker skeleton exists
Risks to avoid
too many states
giant taxonomy
mixing provider logic into schema sprint
Sprint 2 — Closet upload and draft flow
Goal

Let the user create a draft and upload a private image safely.

Deliver
create draft
signed upload intent
finalize upload
review inbox entry
content hash + validation
idempotent create/finalize
Acceptance
user can upload one image into a draft
finalize works once safely
invalid uploads are rejected cleanly
draft appears in review flow
Risks to avoid
direct public uploads
duplicate draft creation
missing ownership checks
Sprint 3 — Closet image processing
Goal

Produce a usable closet image.

Deliver
EXIF normalization
thumbnail generation
background removal integration
processed asset generation
fallback behavior
processing status endpoint
Acceptance
item gets processed image or fallback original
status visible to client
failed steps can be retried
provider output is tracked
Risks to avoid
hard-failing item creation on cutout failure
no fallback image
non-resumable pipeline
Sprint 4 — Closet metadata extraction
Goal

Extract raw clothing metadata from the best image available.

Deliver
provider adapter for metadata extraction
raw provider payload persistence
candidate attribute generation
extraction status
reextract action
Acceptance
raw extraction runs async
raw payload is stored
partial extraction is supported
extraction failure never destroys item
Risks to avoid
letting vendor output become canonical truth
no append-only record
brittle JSON parsing without recovery
Sprint 5 — Metadata normalization and trust layer
Goal

Turn messy extraction into usable closet data.

Deliver
normalization rules
taxonomy mapping
confidence propagation
applicability handling
field states
metadata projection builder
Acceptance
fields can be value/unknown/not_applicable
source/confidence/review state are visible
projection rebuild is deterministic
searchable confirmed metadata model exists
Risks to avoid
full ontology explosion
hiding uncertainty
mixing user truth with provider truth
Sprint 6 — Confirmation and editing
Goal

Give the user control over the final closet truth.

Deliver
review endpoint
edit endpoint
confirm action
manual overrides
retry actions
audit events for edits
Acceptance
user can edit fields
user can clear values
user can mark not applicable
item confirms only when minimum required fields are present
Risks to avoid
overblocking confirmation
losing AI suggestions after manual edit
no stale-review protection
Sprint 7 — Browse, search, filter, detail
Goal

Make the closet actually usable.

Deliver
confirmed closet list
detail view
search/filter API
cursor pagination
review queue separation
history endpoint optional
Acceptance
confirmed items are browsable
filter/search works on structured fields
detail page returns clean item data
mobile and web can use the same contracts
Risks to avoid
exposing unconfirmed noisy items by default
weak pagination
search built on raw non-normalized fields
Sprint 8 — Similarity and duplicate detection
Goal

Keep the closet clean and useful.

Deliver
perceptual hash pipeline
similarity scoring
explainable signal breakdown
duplicate/similar endpoints
dismiss / mark duplicate actions
Acceptance
confirmed items generate similarity candidates
result includes explanation
user can dismiss false positives
no auto-merge required
Risks to avoid
embeddings becoming mandatory
black-box scoring
auto-destructive merge behavior
18. Git and PR strategy

Use one branch per sprint, merged in order.

Branch naming:

phase-04/s1-schema-lifecycle
phase-04/s2-upload-draft
phase-04/s3-image-processing
phase-04/s4-metadata-extraction
phase-04/s5-normalization-trust
phase-04/s6-confirmation-editing
phase-04/s7-browse-search-detail
phase-04/s8-similarity-duplicates
PR structure

Prefer 1–3 PRs max per sprint:

schema/services
worker/provider integration
client integration

Never keep multiple schema-heavy PRs open at once.

19. Biggest risks
Taxonomy bloat

Fix by locking a small versioned MVP taxonomy early.

Provider unreliability

Fix by preserving manual fallback everywhere.

State-machine overengineering

Fix by keeping lifecycle/process/review statuses minimal.

Noisy closet quality

Fix by requiring confirmation before item becomes closet truth.

Duplicate detection false positives

Fix by making similarity a review aid, not an automatic merge tool.

20. Final strategic recommendation

The closet should be built around this mental model:

photo → draft → processing → AI suggestions → trust layer → human confirmation → confirmed closet → similarity intelligence

That is the right backbone.

Not:

photo → AI → auto-save
photo → giant fashion ontology
photo → expensive ML stack
photo → social feed

Your MVP wins if it feels like this:

easy to add clothes
smart enough to save effort
honest about uncertainty
clean after confirmation
useful to browse
ready for “should I buy this?” later

That is the best version of the Tenue closet.