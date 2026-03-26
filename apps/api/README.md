# apps/api

FastAPI + SQLAlchemy + Alembic backend scaffold for Tenue.

Rules:

- this app remains a normal Python project
- it must not be added to `pnpm-workspace.yaml`
- it must not receive a fake `package.json`
- root orchestration reaches it through `scripts/api/*.sh`
- Alembic remains the application migration authority

Phase 03 adds the first real backend slice:

- one app-owned `users` table
- a dedicated `auth` domain
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- Supabase Auth wrapped behind an API-side adapter
- reusable protected-user dependency for future routes

Still out of scope:

- closet and any product-domain behavior
- direct client access to Supabase Auth
- profile enrichment beyond auth identity
