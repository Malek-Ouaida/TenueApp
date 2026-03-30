# apps/api

FastAPI + SQLAlchemy + Alembic backend for Tenue.

Rules:

- this app remains a normal Python project
- it must not be added to `pnpm-workspace.yaml`
- it must not receive a fake `package.json`
- root orchestration reaches it through `scripts/api/*.sh`
- Alembic remains the application migration authority

Current implemented backend slices:

- auth foundation with API-owned users plus `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, and `GET /auth/me`
- profile identity foundation under `/profiles/*`
- closet draft creation, secure upload finalization, review inbox, image processing, metadata extraction, normalization/review, confirmation, browse/detail, and similarity/duplicate detection

Closet worker usage:

- `PYTHONPATH=. uv run python -m app.domains.closet.worker_runner`
- add `--once` to process one pending job and exit
- add `--enqueue-similarity-backfill` to enqueue similarity recompute jobs for confirmed items that do not yet have a completed similarity run

Still out of scope:

- direct client access to Supabase Auth
- web/mobile closet UI implementation
- downstream stylist, shopping, lookbook, stats, and try-on features
