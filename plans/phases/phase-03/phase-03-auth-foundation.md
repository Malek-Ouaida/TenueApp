# Phase 03 -- Auth foundation

## Goal

Establish the auth foundation across `apps/api`, `apps/mobile`, and `apps/web` without starting closet or any other product-domain feature.

## Scope

- add the first real `auth` domain slice in `apps/api`
- create an app-owned `users` table for canonical application identity
- implement `POST /auth/register`
- implement `POST /auth/login`
- implement `POST /auth/refresh`
- implement `POST /auth/logout`
- implement `GET /auth/me`
- add a reusable protected user-scope dependency in the API
- wire mobile auth flows against the API with secure local session persistence
- wire web auth flows against the API with `HttpOnly` cookie session orchestration
- add auth env/config requirements for API, mobile, and web
- add automated API tests and focused client smoke validation

## Non-goals

- closet, outfits, lookbook, stylist, purchase evaluation, insights, or try-on
- profile editing beyond the minimal auth-backed user record
- direct Supabase Auth integration from mobile or web
- direct database access from clients
- social login, magic links, MFA, password reset, or RLS work
- custom Tenue JWT issuance

## Deliverables

- `apps/api` owns the auth HTTP contract and business flow
- Supabase Auth is wrapped behind an API-side provider adapter
- the database has an app-owned `users` table
- register, login, refresh, logout, and `me` work end-to-end
- future protected API routes can reuse the current-user dependency
- mobile can register, login, restore a session, and logout
- web can register, login, restore a session, and logout
- repo docs describe the auth env contract and validation flow

## Exact files/folders to create or change

Create:

- `plans/phases/phase-03/phase-03-auth-foundation.md`
- `plans/sprints/phase-03/phase-03-1-backend-auth-foundation.md`
- `plans/sprints/phase-03/phase-03-2-mobile-auth-integration.md`
- `plans/sprints/phase-03/phase-03-3-web-auth-integration.md`
- `apps/api/app/api/dependencies/auth.py`
- `apps/api/app/api/routes/auth.py`
- `apps/api/app/api/schemas/auth.py`
- `apps/api/app/domains/auth/`
- `apps/api/alembic/versions/0002_phase_03_auth_foundation.py`
- `apps/api/tests/conftest.py`
- `apps/api/tests/test_auth.py`
- `apps/mobile/app/(auth)/login.tsx`
- `apps/mobile/app/(auth)/register.tsx`
- `apps/mobile/app/(app)/index.tsx`
- `apps/mobile/src/lib/api.ts`
- `apps/mobile/src/lib/config.ts`
- `apps/mobile/src/auth/client.ts`
- `apps/mobile/src/auth/provider.tsx`
- `apps/mobile/src/auth/storage.ts`
- `apps/mobile/src/auth/types.ts`
- `apps/web/src/app/(auth)/login/page.tsx`
- `apps/web/src/app/(auth)/register/page.tsx`
- `apps/web/src/app/(app)/layout.tsx`
- `apps/web/src/app/(app)/page.tsx`
- `apps/web/src/app/actions/auth.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/auth/cookies.ts`
- `apps/web/src/lib/auth/session.ts`

Change:

- `README.md`
- `docs/setup/local-infra.md`
- `apps/api/.env.example`
- `apps/api/README.md`
- `apps/api/pyproject.toml`
- `apps/api/app/api/router.py`
- `apps/api/app/core/config.py`
- `apps/api/app/db/base.py`
- `apps/mobile/.env.example`
- `apps/mobile/README.md`
- `apps/mobile/app/_layout.tsx`
- `apps/mobile/package.json`
- `apps/mobile/tsconfig.json`
- `apps/web/.env.example`
- `apps/web/README.md`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/app/globals.css`

## Architecture constraints

- `apps/api` remains the single source of backend auth business logic and HTTP contracts
- auth stays isolated from all product domains
- mobile and web must not call Supabase Auth directly
- mobile and web must not access the database directly
- Supabase remains an infrastructure dependency behind an API-side adapter
- the API reuses provider-issued access and refresh tokens instead of minting its own JWTs
- this phase must not add closet or downstream product logic

## Definition of done

- register, login, refresh, logout, and `me` work end-to-end through `apps/api`
- an app-owned `users` table exists and is populated consistently from auth flows
- authenticated API scope can resolve the current app user
- mobile can sign up, sign in, restore a session, and sign out
- web can sign up, sign in, refresh a protected page, and sign out
- auth env requirements are documented and reflected in env examples
- API auth tests pass
- no closet or other product-domain behavior was added

## Validation/checks to run

- `pnpm infra:up`
- `pnpm db:migrate`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`
- `cd apps/api && PYTHONPATH=. uv run pytest tests/test_auth.py`
- `curl -sS -X POST http://127.0.0.1:8000/auth/register`
- `curl -sS -X POST http://127.0.0.1:8000/auth/login`
- `curl -sS http://127.0.0.1:8000/auth/me -H "Authorization: Bearer <access-token>"`
- mobile smoke: register, login, relaunch app, logout
- web smoke: register, login, reload protected page, logout
