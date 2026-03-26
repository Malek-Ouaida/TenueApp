# Phase 02 -- Infra and developer experience

## Goal

Add the minimum local infrastructure and developer workflows needed to evolve the API scaffold safely without introducing auth, closet, or later-phase product behavior.

## Scope

- use the local Supabase stack for Postgres only
- keep schema migration ownership in `apps/api` with Alembic
- add MinIO as the Phase 02 local object-storage service
- replace the SQLite migration assumption with an env-driven Postgres `DATABASE_URL`
- add a minimal SQLAlchemy engine/session foundation in `apps/api`
- add app-specific env examples for API, web, and mobile
- add root-facing infra and database workflow scripts
- document the local setup and update repo docs to Phase 02
- add one DB smoke test and a baseline empty migration

## Non-goals

This phase must not include:

- Supabase Auth integration
- Supabase client SDK wiring in web or mobile
- RLS policy work
- closet models or product-domain tables
- uploads or storage API integration
- object-processing or provider logic
- any auth, closet, stylist, lookbook, or shopping behavior

## Deliverables

By the end of Phase 02:

- local Supabase can provide the development Postgres instance
- MinIO can provide local object storage with one bootstrap bucket
- Alembic runs against Postgres through `DATABASE_URL`
- the API has a reusable SQLAlchemy engine/session module
- root commands exist for infra lifecycle and DB migrations
- app-specific env examples exist for API, web, and mobile
- documentation reflects the real local workflow
- one DB smoke test exists without making the default test flow depend on running infra

## Exact files/folders to create

- `plans/phases/phase-02/phase-02-infra-and-dx.md`
- `supabase/config.toml`
- `infra/local/compose.yaml`
- `docs/setup/local-infra.md`
- `scripts/infra/up.sh`
- `scripts/infra/down.sh`
- `scripts/infra/status.sh`
- `scripts/api/migrate.sh`
- `scripts/api/revision.sh`
- `apps/api/.env.example`
- `apps/web/.env.example`
- `apps/mobile/.env.example`
- `apps/api/app/db/session.py`
- `apps/api/alembic/versions/0001_phase_02_baseline.py`
- `apps/api/tests/test_db_smoke.py`

## Existing files to change

- `package.json`
- `.env.example`
- `.gitignore`
- `README.md`
- `infra/README.md`
- `scripts/README.md`
- `apps/api/README.md`
- `apps/api/pyproject.toml`
- `apps/api/alembic.ini`
- `apps/api/alembic/env.py`
- `apps/api/app/core/config.py`
- `scripts/api/test.sh`

## Implementation details

### Local infrastructure

- use `supabase/config.toml` to define the local Supabase project and standard local DB port
- use `supabase start`, `supabase stop`, and `supabase status` for the local database stack
- use `infra/local/compose.yaml` only for MinIO and its one-shot bucket bootstrap container
- keep the app connected only to the local Postgres endpoint from Supabase
- treat Supabase services other than Postgres as out of scope for this phase even if the local stack starts them

### Database workflow

- add `DATABASE_URL` to the API env contract
- default it to the local Supabase Postgres URL for developer convenience
- keep Alembic as the only schema migration authority
- create an empty baseline migration for the Phase 02 DB foundation
- add root commands:
  - `pnpm db:migrate`
  - `pnpm db:revision -- "message"`

### API database foundation

- keep the current sync SQLAlchemy approach
- add a central engine and session factory in `apps/api/app/db/session.py`
- keep route handlers thin and do not introduce repositories, models, or domain services yet
- do not make the health endpoint depend on the database

### Environment handling

- keep root `.env.example` limited to shared repo-level values
- add `apps/api/.env.example` for API runtime values
- add `apps/web/.env.example` and `apps/mobile/.env.example` for client-local API base URLs only
- do not put direct database credentials in web or mobile env files

## Validation/checks

- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`
- `pnpm infra:up`
- `pnpm infra:status`
- `pnpm db:migrate`
- `cd apps/api && PYTHONPATH=. uv run alembic current`
- `pnpm dev:api`
- `curl -sS http://127.0.0.1:8000/health`
- `cd apps/api && PYTHONPATH=. uv run pytest tests/test_db_smoke.py`
- confirm MinIO health responds on `http://127.0.0.1:9000/minio/health/live`
- confirm the `tenue-dev` bucket exists
- confirm `apps/api` remains outside `pnpm-workspace.yaml`

## Assumptions

- local database development uses Supabase CLI and Docker
- local object storage remains MinIO in this phase
- Alembic is the single migration system for application-owned schema changes
- `pnpm dev` does not auto-start infrastructure
- Python remains pinned to 3.12 even if a local machine has other versions installed

## Risks

- the repo previously documented “Supabase later” and “Postgres + MinIO only,” so doc drift must be corrected everywhere in this phase
- local Supabase and MinIO port conflicts may appear on developer machines
- the local machine may not have the Supabase CLI installed yet
- the Python interpreter actually used by a developer may drift from the repo’s pinned version
- a second migration system could be introduced later unless the docs keep Alembic ownership explicit
