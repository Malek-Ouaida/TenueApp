# Phase 01 -- App scaffolds

## Goal

Create real, minimal application shells for:

- `apps/mobile` as Expo + React Native + TypeScript + Expo Router
- `apps/web` as Next.js + TypeScript + App Router
- `apps/api` as FastAPI + SQLAlchemy + Alembic

This phase exists to make the three app surfaces runnable and structurally aligned with the architecture, without implementing product-domain behavior.

## Scope

This phase includes only scaffold-level work:

- turn `apps/mobile` into a real Expo Router application shell
- turn `apps/web` into a real Next.js App Router application shell
- turn `apps/api` into a real FastAPI Python application shell
- make the existing root script contract from Phase 00 resolve against real apps
- add only the minimum routes/screens/endpoints needed to prove the shells are real
- keep mobile and web as thin clients
- keep the API as a thin transport shell with one minimal typed endpoint
- minimally adjust existing shared config packages only if required to support real Expo/Next app configs

## Non-goals

This phase must not include:

- auth flows, auth routes, auth state, or user sessions
- closet models, closet APIs, closet screens, or closet UI
- database models, repositories, migrations, or runtime DB connectivity
- storage, uploads, MinIO, S3, or media pipelines
- Supabase
- AI features
- provider adapters
- shared runtime UI packages
- shared API client packages
- generated OpenAPI TypeScript packages
- frontend networking/data fetching
- state-management frameworks beyond framework defaults
- background jobs, workers, or queues
- any domain logic beyond a health endpoint

## Deliverables

By the end of Phase 01:

- `pnpm dev:mobile` launches a real Expo app shell
- `pnpm dev:web` launches a real Next.js app shell
- `pnpm dev:api` launches a real FastAPI app shell
- `pnpm dev` launches all three together
- `pnpm lint` works across the scaffolded JS/TS apps and the Python API wrapper
- `pnpm typecheck` works across the scaffolded JS/TS apps and the Python API wrapper
- `pnpm test` works with at least one real API smoke test and explicit frontend placeholder test scripts
- `pnpm format` works under the same scaffold contract
- mobile has a real root route
- web has a real root route
- API has a real `GET /health` endpoint
- `apps/api` remains outside `pnpm-workspace.yaml`

## Exact files/folders to create

### Root changes

- change `README.md` to reflect that the repo is now in Phase 01 scaffold state
- change `packages/config-typescript/expo.json` so it is compatible with a real Expo app
- change `packages/config-typescript/next.json` so it is compatible with a real Next.js app

### Mobile scaffold

- `apps/mobile/package.json`
- `apps/mobile/app.json`
- `apps/mobile/babel.config.js`
- `apps/mobile/tsconfig.json`
- `apps/mobile/eslint.config.mjs`
- `apps/mobile/expo-env.d.ts`
- `apps/mobile/app/_layout.tsx`
- `apps/mobile/app/index.tsx`
- `apps/mobile/app/+not-found.tsx`
- `apps/mobile/README.md`

### Web scaffold

- `apps/web/package.json`
- `apps/web/next.config.ts`
- `apps/web/tsconfig.json`
- `apps/web/eslint.config.mjs`
- `apps/web/next-env.d.ts`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/globals.css`
- `apps/web/README.md`

### API scaffold

- `apps/api/pyproject.toml`
- `apps/api/alembic.ini`
- `apps/api/app/__init__.py`
- `apps/api/app/main.py`
- `apps/api/app/api/__init__.py`
- `apps/api/app/api/router.py`
- `apps/api/app/api/routes/__init__.py`
- `apps/api/app/api/routes/health.py`
- `apps/api/app/api/schemas/__init__.py`
- `apps/api/app/api/schemas/health.py`
- `apps/api/app/core/__init__.py`
- `apps/api/app/core/config.py`
- `apps/api/app/db/__init__.py`
- `apps/api/app/db/base.py`
- `apps/api/alembic/env.py`
- `apps/api/alembic/script.py.mako`
- `apps/api/alembic/versions/.gitkeep`
- `apps/api/tests/test_health.py`
- `apps/api/README.md`

## App-specific scaffold details

### Mobile scaffold details

#### Why this shape

This follows `AGENTS.md` and `ARCHITECTURE.md`:

- mobile is the primary product surface
- clients should own UX flow and display logic only
- product logic must not live in the client
- this phase is scaffolding only

#### What to scaffold

Create a minimal Expo Router app with:

- package name: `@tenue/mobile`
- real `dev`, `lint`, `typecheck`, `test`, and `format` scripts
- Expo Router entrypoint via `main`
- one root route at `/`
- one root router layout
- one not-found route
- TypeScript config using the shared TS package
- ESLint config using the shared ESLint package

#### Minimal file structure

```text
apps/mobile/
  package.json
  app.json
  babel.config.js
  tsconfig.json
  eslint.config.mjs
  expo-env.d.ts
  app/
    _layout.tsx
    index.tsx
    +not-found.tsx
```

#### Minimal route/screen behavior

- `/` renders a plain scaffold screen with app name and scaffold-only copy
- `_layout.tsx` sets up a minimal stack layout only
- `+not-found.tsx` handles unknown routes
- no tabs
- no auth stack
- no data fetching
- no API client
- no domain UI
- no design system package
- no local persistence

#### Mobile package scripts

- `dev`: `expo start`
- `lint`: `eslint .`
- `typecheck`: `tsc --noEmit`
- `test`: explicit placeholder success script
- `format`: explicit placeholder success script

#### Mobile configuration required at scaffold time

- `package.json`
- `app.json`
- `babel.config.js`
- `tsconfig.json`
- `eslint.config.mjs`
- `expo-env.d.ts`

#### Explicitly deferred for mobile

- auth screens
- navigation tabs
- API calls
- shared UI layer
- styling system expansion
- state management library
- image capture
- storage or secure storage
- product screens of any kind

### Web scaffold details

#### Why this shape

This follows `AGENTS.md` and `ARCHITECTURE.md`:

- web is a real secondary surface
- the client remains thin
- no business logic belongs in the web scaffold
- Phase 01 should create a real shell, not a feature app

#### What to scaffold

Create a minimal Next.js App Router app with:

- package name: `@tenue/web`
- `src/app` structure
- one root page at `/`
- one root layout
- one global stylesheet
- TypeScript config using the shared TS package
- ESLint config using the shared ESLint package

#### Minimal file structure

```text
apps/web/
  package.json
  next.config.ts
  tsconfig.json
  eslint.config.mjs
  next-env.d.ts
  src/
    app/
      layout.tsx
      page.tsx
      globals.css
```

#### Minimal route behavior

- `/` renders a plain scaffold page only
- no API routes
- no auth routes
- no server actions for product behavior
- no data fetching
- no shared UI package
- no Tailwind unless it becomes absolutely required by the chosen scaffold path; default recommendation is do not add it

#### Web package scripts

- `dev`: `next dev`
- `build`: `next build`
- `start`: `next start`
- `lint`: `eslint .`
- `typecheck`: `tsc --noEmit`
- `test`: explicit placeholder success script
- `format`: explicit placeholder success script

#### Web configuration required at scaffold time

- `package.json`
- `next.config.ts`
- `tsconfig.json`
- `eslint.config.mjs`
- `next-env.d.ts`

#### Explicitly deferred for web

- auth pages
- product pages
- API client layer
- data fetching
- edge/runtime decisions beyond default Next behavior
- shared UI system
- design tokens package
- analytics
- middleware

### API scaffold details

#### Why this shape

This follows `ARCHITECTURE.md` directly:

- backend is a modular monolith
- route handlers are transport only
- API contracts belong to the backend
- explicit schemas are preferred
- business logic must not be buried in HTTP handlers

It also follows `AGENTS.md`:

- FastAPI is the single source of backend business logic
- this phase is scaffolding only
- no product-domain implementation yet

#### What to scaffold

Create a real FastAPI Python project with:

- `uv`-managed `pyproject.toml`
- FastAPI, Uvicorn, SQLAlchemy, and Alembic installed
- Ruff, Mypy, Pytest, and HTTPX for dev/test tooling
- entrypoint at `app.main:app` so existing root wrappers work
- router wiring through `app/api/router.py`
- one typed health endpoint at `GET /health`
- SQLAlchemy base scaffold present but unused for domain models
- Alembic scaffold present but unused for real revisions

#### Minimal file structure

```text
apps/api/
  pyproject.toml
  alembic.ini
  app/
    __init__.py
    main.py
    api/
      __init__.py
      router.py
      routes/
        __init__.py
        health.py
      schemas/
        __init__.py
        health.py
    core/
      __init__.py
      config.py
    db/
      __init__.py
      base.py
  alembic/
    env.py
    script.py.mako
    versions/
      .gitkeep
  tests/
    test_health.py
```

#### Minimal endpoint behavior

- `GET /health` returns `200`
- response body is a typed JSON object
- response model should live in `app/api/schemas/health.py`
- no auth routes
- no closet routes
- no DB session dependency
- no ORM model exposure
- no migrations created
- no provider integrations
- no background jobs

#### API scripts that must work through existing wrappers

The existing root wrapper scripts should work unchanged:

- `scripts/api/dev.sh` -> `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- `scripts/api/lint.sh` -> `uv run ruff check .`
- `scripts/api/typecheck.sh` -> `uv run mypy .`
- `scripts/api/test.sh` -> `uv run pytest`
- `scripts/api/format.sh` -> `uv run ruff format .`

#### API configuration required at scaffold time

- `pyproject.toml`
- `alembic.ini`
- `app/core/config.py`
- Alembic environment files
- tool config inside `pyproject.toml` where practical

#### Explicitly deferred for API

- auth routers
- closet routers
- SQLAlchemy models
- repository layer
- service layer with product logic
- DB engine/session runtime setup beyond the minimum required Alembic scaffold
- migrations/revisions
- object storage
- provider adapters
- background orchestration
- OpenAPI client generation
- Supabase

## Root scripts that must work after this phase

The following root scripts already exist and should become real after Phase 01:

- `pnpm dev`
- `pnpm dev:mobile`
- `pnpm dev:web`
- `pnpm dev:api`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`
- `pnpm format`

### Required script behavior after Phase 01

- `pnpm dev:mobile` runs the Expo shell
- `pnpm dev:web` runs the Next.js shell
- `pnpm dev:api` runs the FastAPI shell
- `pnpm dev` launches all three together
- `pnpm lint` lints mobile and web via Turbo, then the API via the existing shell wrapper
- `pnpm typecheck` typechecks mobile and web via Turbo, then the API via the existing shell wrapper
- `pnpm test` runs explicit scaffold-level checks and the API health test
- `pnpm format` runs explicit scaffold-level format contract and the API formatter

## Minimal changes needed to shared config packages

Phase 01 should keep `packages/` minimal, but one small compatibility adjustment is justified:

- `packages/config-typescript/expo.json` should be made Expo-compatible for a real Expo app
- `packages/config-typescript/next.json` should be made Next-compatible for a real Next app

No new shared packages should be created.
No shared runtime code should be introduced.
No `packages/api-client` or `packages/ui` should be created in this phase.

## Architecture constraints, made explicit section by section

### From `AGENTS.md`

- clients stay thin
- mobile-first matters, but no feature implementation yet
- FastAPI owns backend business logic
- preserve architecture boundaries
- do not introduce unnecessary conventions
- run tests/lint/typecheck where available

### From `ARCHITECTURE.md`

- `apps/api` is one backend application
- route handlers stay thin
- API uses explicit schemas
- backend contracts are owned by the backend
- web/mobile are product surfaces, not business-logic owners
- provider integrations remain absent in this phase
- do not overbuild domains before the feature phases

### From `ROADMAP.md`

- this phase stops at app shells
- no auth, closet, or downstream features
- success is scaffolds running, not product progress

### Hard boundary for `apps/api`

- `apps/api` must remain outside `pnpm-workspace.yaml`
- `apps/api` must remain a normal Python project
- no fake `package.json` should be added to `apps/api`

## Risks and bad decisions to avoid

- letting the scaffold generators dictate architecture instead of adapting them to the repo
- accidentally adding auth pages or auth routes “just because they are easy”
- adding Tailwind, shared UI packages, or shared API clients without real need
- creating SQLAlchemy models or migrations too early
- making health checks depend on a real database
- adding frontend data fetching in a scaffold phase
- putting business logic in the API route file
- introducing Supabase anywhere in this phase
- creating domain directories filled with fake code just to look “architected”
- changing the Phase 00 root contract instead of making it real

## Definition of done

Phase 01 is done only when:

- `apps/mobile` is a real Expo Router app shell
- `apps/web` is a real Next.js App Router app shell
- `apps/api` is a real FastAPI project shell
- the root scripts work against real apps
- `apps/api` is still outside `pnpm` workspaces
- the API exposes `GET /health`
- mobile `/` and web `/` render scaffold-only screens/pages
- no auth, closet, storage, Supabase, AI, or product-domain logic was added

## Validation/checks to run

### Root-level validation

- `pnpm install`
- `pnpm dev:mobile`
- `pnpm dev:web`
- `pnpm dev:api`
- `pnpm dev`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`
- `pnpm format`

### Mobile validation

- confirm Expo boots successfully
- confirm Expo Router resolves `/`
- confirm unknown routes resolve to `+not-found`

### Web validation

- `pnpm --filter @tenue/web build`
- confirm `http://127.0.0.1:3000/` renders the scaffold page

### API validation

- confirm FastAPI boots via the existing root script
- confirm `curl http://127.0.0.1:8000/health` returns `200`
- confirm `/docs` and `/openapi.json` load
- run the API test suite and confirm `tests/test_health.py` passes

### Boundary validation

- verify `pnpm-workspace.yaml` still excludes `apps/api`
- verify no new shared runtime package was added under `packages/`
- verify no auth, closet, storage, Supabase, or AI files exist after the phase

## Assumptions and defaults

- frontend `test` and `format` scripts may remain explicit placeholder success scripts in Phase 01; deeper frontend quality-tooling setup belongs to Phase 02
- API testing is real in Phase 01 because the backend shell should expose a real HTTP contract immediately
- FastAPI docs remain enabled by default
- Alembic is scaffolded structurally only; no revision should be created in this phase
- existing root API wrapper scripts are kept and satisfied rather than replaced
