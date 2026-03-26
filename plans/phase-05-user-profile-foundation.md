# Phase 05 -- User profile foundation

## Goal

Create the backend and client foundations for profile identity so Tenue has a real authenticated profile shell on mobile and web without pulling in lookbook, stats, or social-platform behavior.

## Scope

- extend the app-owned `users` record with `username`, `display_name`, `bio`, and a nullable avatar reference
- add `GET /profiles/me`
- add `PATCH /profiles/me`
- add `GET /profiles/{username}` for future username-based profile routing
- enforce backend-owned username validation and uniqueness rules
- ship authenticated self-profile screens at `/profile` on web and mobile
- redirect `/` to `/profile` until a broader app home exists
- render a strong profile header plus grid-based placeholder sections for future lookbook and stats content

## Non-goals

- lookbook implementation
- stats or insights computation
- outfit history
- follower/following systems or social features
- public profile rollout
- avatar upload, picker, storage, or image-processing pipeline
- closet or other product-domain aggregation beyond static placeholders

## Deliverables

- stable profile read/update API contract
- backend-owned username normalization, validation, and uniqueness handling
- authenticated “my profile” flow on mobile and web
- profile shell UI with avatar placeholder/support, username, display name, bio, and edit controls
- future profile-route strategy documented as `/u/[username]` without shipping a public profile page yet

## Exact files/folders to create or change

Create:

- `plans/phase-05-user-profile-foundation.md`
- `apps/api/app/api/dependencies/profile.py`, `apps/api/app/api/routes/profile.py`, `apps/api/app/api/schemas/profile.py`
- `apps/api/app/domains/profile/__init__.py`, `apps/api/app/domains/profile/repository.py`, `apps/api/app/domains/profile/service.py`
- `apps/api/alembic/versions/0003_phase_05_user_profile_foundation.py`
- `apps/api/tests/test_profile.py`
- `apps/mobile/app/(app)/profile.tsx`, `apps/mobile/src/profile/client.ts`, `apps/mobile/src/profile/types.ts`
- `apps/web/src/app/(app)/profile/page.tsx`, `apps/web/src/app/actions/profile.ts`, `apps/web/src/components/profile/ProfilePage.tsx`, `apps/web/src/lib/profile.ts`

Change:

- `apps/api/app/api/router.py`, `apps/api/app/domains/auth/models.py`
- `apps/mobile/app/(app)/index.tsx`
- `apps/web/src/app/(app)/layout.tsx`, `apps/web/src/app/(app)/page.tsx`, `apps/web/src/app/globals.css`
- `README.md`
- `ROADMAP.md` if this phase is adopted into the official sequence

## Architecture constraints

- `apps/api` remains the single source of profile business logic and HTTP contracts
- `GET /auth/me` remains the auth/session contract; profile identity lives under `/profiles/*`
- profile fields are stored on `users`, but profile use-cases live in a dedicated service/repository layer
- username is stored lowercase and enforced unique at both service and database levels
- `GET /profiles/{username}` stays auth-protected in this phase
- clients stay thin and only consume the API over HTTP
- no avatar upload flow, no social counters, and no downstream content aggregation in this phase

## Definition of done

- authenticated users can load `/profiles/me` and update username, display name, and bio through `PATCH /profiles/me`
- username validation, reserved-name rejection, and duplicate handling work consistently
- web and mobile both render a real profile shell with a strong header and placeholder content grid
- `/` redirects to `/profile` on both clients where applicable
- `GET /profiles/{username}` returns the same profile shell data shape needed for future route expansion
- no lookbook, stats, social, or avatar-upload behavior was added

## Validation/checks to run

- `pnpm db:migrate`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`
- `cd apps/api && PYTHONPATH=. uv run pytest tests/test_profile.py`
- API smoke: register/login, `GET /profiles/me`, `PATCH /profiles/me`, duplicate username rejection, `GET /profiles/{username}`
- mobile smoke: login, land on `/profile`, edit username/display name/bio, relaunch and verify persistence
- web smoke: login, redirect to `/profile`, edit username/display name/bio, reload and verify persistence and placeholder sections
