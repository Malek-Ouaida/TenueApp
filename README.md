# Tenue

Tenue is an AI-powered closet companion with a closet-first architecture.

This repository is currently at **Phase 03: auth foundation**. The goal of this phase is to establish user identity, session handling, protected user scope, and thin client auth integration without implementing any product-domain behavior yet.

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

- `apps/mobile` now includes register/login screens, secure session persistence, and a protected shell
- `apps/web` now includes register/login pages, cookie-backed session handling, and a protected shell
- `apps/api` now includes a dedicated auth domain, a `users` table, and auth endpoints
- Alembic is configured for an env-driven Postgres database URL
- local infra workflows exist for Supabase Postgres and MinIO
- no closet, uploads, storage integration, or AI features have been implemented yet

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

## Workspace rules

- `apps/api` is a Python project and **must not** be added to `pnpm-workspace.yaml`
- FastAPI remains the single source of backend business logic and API contracts
- web and mobile consume backend contracts over HTTP only
- Supabase Auth is used only behind the API auth adapter
- OpenAPI-generated TypeScript types should eventually live in `packages/api-types`
- no `packages/shared` dumping ground
- no shared backend business-logic package

## Infrastructure rules

- Supabase is used as local infrastructure for Postgres in Phase 03
- MinIO remains the local object-storage service in Phase 03
- Alembic in `apps/api` remains the only migration authority for application-owned schema
- web and mobile do not connect directly to the database
- `pnpm dev` does not start local infra automatically

## Phase plans

- roadmap: [ROADMAP.md](./ROADMAP.md)
- architecture: [ARCHITECTURE.md](./ARCHITECTURE.md)
- agent guidance: [AGENTS.md](./AGENTS.md)
- Phase 00 plan: [plans/phases/phase-00/phase-00-monorepo-foundation.md](./plans/phases/phase-00/phase-00-monorepo-foundation.md)
- Phase 01 plan: [plans/phases/phase-01/phase-01-app-scaffolds.md](./plans/phases/phase-01/phase-01-app-scaffolds.md)
- Phase 03 plan: [plans/phases/phase-03/phase-03-auth-foundation.md](./plans/phases/phase-03/phase-03-auth-foundation.md)
