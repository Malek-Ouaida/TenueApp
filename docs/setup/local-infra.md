# Local Infra Setup

Phase 03 local development uses:

- Supabase local stack for Postgres
- MinIO for object storage
- Alembic for application-owned schema migrations

## Prerequisites

- Node 22+
- `pnpm`
- Python 3.12
- `uv`
- Docker + Docker Compose
- Supabase CLI

The Supabase CLI can be installed globally, or made available through the repo-local `node_modules/.bin/supabase`. The infra scripts resolve either option automatically.

## Env setup

Copy the env examples before starting the stack:

```bash
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
cp apps/mobile/.env.example apps/mobile/.env
```

After the stack is up, copy the local Supabase publishable key into `apps/api/.env`:

```bash
pnpm infra:status
```

Use the reported API gateway URL for `SUPABASE_URL` if you are not using the default `http://127.0.0.1:54321`, then set `SUPABASE_PUBLISHABLE_KEY` from the same status output. Older Supabase setups can keep using `SUPABASE_ANON_KEY`; the API accepts either env name.

## Start local infra

```bash
pnpm infra:up
pnpm infra:status
```

Phase 02 ports:

- Supabase API gateway: `54321` (unused by the app in this phase)
- Supabase Postgres: `54322`
- Supabase Studio: `54323`
- MinIO API: `9000`
- MinIO Console: `9001`

The default local Postgres URL is:

```text
postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres
```

For a hosted Supabase project, the API expects a SQLAlchemy URL using the `psycopg` driver:

```text
postgresql+psycopg://postgres.<project_ref>:<password>@<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

If your hosted password contains reserved URL characters, URL-encode it before putting it in `DATABASE_URL`.

The default MinIO bucket is:

```text
tenue-dev
```

## Run migrations

```bash
pnpm db:migrate
cd apps/api && PYTHONPATH=. uv run alembic current
```

## Run the API

```bash
pnpm dev:api
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/auth/me -H "Authorization: Bearer <access-token>"
```

## DB smoke test

The default root test flow excludes DB integration tests so local infrastructure is not required for every edit. Run the DB smoke test explicitly after bringing infra up:

```bash
cd apps/api && PYTHONPATH=. uv run pytest tests/test_db_smoke.py
cd apps/api && PYTHONPATH=. uv run pytest tests/test_auth.py
```

## Storage checks

After `pnpm infra:up`, confirm MinIO is healthy:

```bash
curl -sS http://127.0.0.1:9000/minio/health/live
```

Then confirm the `tenue-dev` bucket exists from the MinIO console or with your preferred S3 client.

## Stop local infra

```bash
pnpm infra:down
```

`pnpm dev` does not start infrastructure automatically in Phase 03.
