# Infra

This directory is for local development infrastructure and later deployment configuration.

- `local/`: Docker Compose for local non-Supabase services beginning in Phase 02
- `deploy/`: deployment-specific configuration for later environments

Rules:

- Phase 02 uses the local Supabase stack for Postgres
- Phase 02 uses `infra/local/compose.yaml` for MinIO only
- Alembic in `apps/api` owns application schema migrations
- Supabase remains infrastructure only in this phase; the app does not integrate Auth or Storage yet
