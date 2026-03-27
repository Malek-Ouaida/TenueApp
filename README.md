# Tenue

Tenue is an AI-powered closet companion with a closet-first architecture.

This repository now includes the **Phase 04 closet ingestion backend foundation** on top of the earlier auth and profile identity slices.

The current implemented product slice is the early closet pipeline:

`photo -> upload draft -> processing/background removal -> AI metadata extraction`

That work is backend-first today. Confirmation/editing, closet browse/detail surfaces, stylist flows, lookbook, stats, and try-on are still later phases.

## Stack

- `apps/mobile`: Expo + React Native + TypeScript
- `apps/web`: Next.js + TypeScript
- `apps/api`: FastAPI + SQLAlchemy + Alembic
- package manager: `pnpm`
- task runner: `turbo`
- Python workflow for the API: `uv`
- local database stack: `supabase`
- local object storage: `minio`

## Prerequisites

- Node 22 LTS
- `pnpm`
- Python 3.12
- `uv`
- Docker
- Docker Compose
- Supabase CLI

## Repo layout

- `apps/`: deployable product surfaces only
- `packages/`: shared JS/TS config and generated contracts
- `infra/`: local service orchestration and later deployment config
- `docs/`: supporting docs, ADRs, and setup notes
- `plans/`: roadmap phase plans and sprint plans
- `scripts/`: thin orchestration wrappers, especially for the Python API

## Workspace policy

- `pnpm-workspace.yaml` includes only `apps/mobile`, `apps/web`, and `packages/*`
- `apps/api` stays outside the pnpm workspace model and remains a normal Python project
- the root lockfile is committed and shared across the JS/TS workspace
- root JS dependencies are pinned exactly
- `.npmrc` enforces workspace-linking and disables peer auto-install so dependency edges stay explicit
- `.gitattributes` and `.editorconfig` enforce consistent line endings and formatting defaults

## Current app state

- `apps/mobile` now includes register/login screens, secure session persistence, and an authenticated `/profile` shell
- `apps/web` now includes register/login pages, cookie-backed session handling, and a profile shell at `/profile`
- `apps/api` now includes a dedicated auth domain, a `users` table, auth endpoints, profile identity endpoints under `/profiles/*`, and the first real closet backend slice
- closet drafts can be created through authenticated APIs, uploaded privately to MinIO/S3-compatible storage, finalized safely, and listed in a review queue
- closet image processing runs asynchronously through the durable worker, producing processed assets, thumbnails, processing snapshots, and manual reprocess support
- raw AI metadata extraction now runs after image processing, stores append-only provider results plus field candidates, and exposes extraction status plus manual re-extract APIs
- Alembic is configured for an env-driven Postgres database URL
- local infra workflows exist for Supabase Postgres and MinIO
- the closet flow is still backend-only; confirmation/editing, confirmed-item browse/detail, and downstream intelligence features are not implemented yet

## Root commands

- `pnpm dev`: starts mobile, web, and API development commands together
- `pnpm dev:mobile`: starts the Expo app shell
- `pnpm dev:web`: starts the Next.js app shell
- `pnpm dev:api`: routes through `scripts/api/dev.sh`
- `pnpm infra:up`: starts the local Supabase database stack and MinIO
- `pnpm infra:down`: stops the local Supabase database stack and MinIO
- `pnpm infra:status`: shows local Supabase and MinIO status
- `pnpm db:migrate`: runs Alembic migrations against the configured database
- `pnpm db:revision -- "message"`: creates a new Alembic revision in `apps/api`
- `pnpm lint`: runs JS/TS workspace lint tasks and the API lint wrapper
- `pnpm typecheck`: runs JS/TS workspace typecheck tasks and the API typecheck wrapper
- `pnpm test`: runs JS/TS workspace test tasks and the API test wrapper
- `pnpm format`: runs JS/TS workspace format tasks and the API format wrapper

For Expo Go on a physical device, `apps/mobile` can derive the local API host from the Metro dev server when `EXPO_PUBLIC_API_BASE_URL` is unset. `pnpm dev:api` now binds the API on `0.0.0.0` by default so devices on the same LAN can reach it.

Closet async jobs currently run through the API worker entrypoint:

```bash
cd apps/api
PYTHONPATH=. uv run python -m app.domains.closet.worker_runner
```

Use `--once` to process at most one queued closet job and exit.

## Workspace rules

- `apps/api` is a Python project and **must not** be added to `pnpm-workspace.yaml`
- FastAPI remains the single source of backend business logic and API contracts
- web and mobile consume backend contracts over HTTP only
- Supabase Auth is used only behind the API auth adapter
- OpenAPI-generated TypeScript types should eventually live in `packages/api-types`
- no `packages/shared` dumping ground
- no shared backend business-logic package

## Infrastructure rules

- Supabase is used as local infrastructure for Postgres in the current foundation
- MinIO remains the local object-storage service for closet ingestion and derived media
- Alembic in `apps/api` remains the only migration authority for application-owned schema
- web and mobile do not connect directly to the database
- `pnpm dev` does not start local infra automatically

## API env notes

- `DATABASE_URL` must use the SQLAlchemy driver form `postgresql+psycopg://...`
- the API accepts `SUPABASE_PUBLISHABLE_KEY` and still falls back to the older `SUPABASE_ANON_KEY` env name
- hosted Supabase session-pooler example: `postgresql+psycopg://postgres.<project_ref>:<password>@<region>.pooler.supabase.com:5432/postgres?sslmode=require`
- `SUPABASE_URL` should be the project base URL such as `https://<project_ref>.supabase.co`
- if your database password contains reserved URL characters, URL-encode it before placing it in `DATABASE_URL`
- `CLOSET_BACKGROUND_REMOVAL_PROVIDER=photoroom` plus `PHOTOROOM_API_KEY` enables background removal; the default stays disabled
- `CLOSET_METADATA_EXTRACTION_PROVIDER=gemini` plus `GEMINI_API_KEY` enables raw metadata extraction; the default stays disabled
- API-specific secrets can live in `apps/api/.env`, which overrides the repo root `.env` for the API process

## Phase plans

- roadmap: [ROADMAP.md](./ROADMAP.md)
- architecture: [ARCHITECTURE.md](./ARCHITECTURE.md)
- agent guidance: [AGENTS.md](./AGENTS.md)
- Phase 00 plan: [plans/phases/phase-00/phase-00-monorepo-foundation.md](./plans/phases/phase-00/phase-00-monorepo-foundation.md)
- Phase 01 plan: [plans/phases/phase-01/phase-01-app-scaffolds.md](./plans/phases/phase-01/phase-01-app-scaffolds.md)
- Phase 03 plan: [plans/phases/phase-03/phase-03-auth-foundation.md](./plans/phases/phase-03/phase-03-auth-foundation.md)
- Phase 04 plan: [plans/phases/phase-04/phase-04-closet-master-plan.md](./plans/phases/phase-04/phase-04-closet-master-plan.md)
- Profile foundation plan: [plans/phase-05-user-profile-foundation.md](./plans/phase-05-user-profile-foundation.md)
