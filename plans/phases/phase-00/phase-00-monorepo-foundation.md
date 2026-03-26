# Phase 00 -- Monorepo foundation

## Goal

Establish the root monorepo skeleton, workspace boundaries, and developer workflow contract for Tenue without scaffolding framework apps or implementing product features.

## Scope

- create the root workspace and task-runner files
- create the top-level repo structure
- create the initial shared JS config packages
- define the root script contract for mobile, web, and API workflows
- reserve clean paths for docs, infra, and generated API contracts
- document toolchain versions and ownership boundaries

## Non-goals

- scaffolding Expo, Next.js, or FastAPI
- implementing auth, closet, or any product domain
- creating database models, migrations, or storage services
- adding Supabase
- creating shared UI or shared runtime domain packages
- generating OpenAPI TypeScript types

## Deliverables

- root tooling files exist
- repo structure exists
- workspace ownership is explicit
- Python API workflow is defined without forcing it into pnpm workspaces
- root command names are standardized
- shared TS/ESLint config packages exist
- prerequisites and boundaries are documented

## Exact files/folders to create

- `package.json`
- `pnpm-workspace.yaml`
- `turbo.json`
- `.npmrc`
- `.gitignore`
- `.gitattributes`
- `.editorconfig`
- `.env.example`
- `README.md`
- `.node-version`
- `.python-version`
- `apps/README.md`
- `apps/mobile/README.md`
- `apps/web/README.md`
- `apps/api/README.md`
- `packages/README.md`
- `packages/config-typescript/package.json`
- `packages/config-typescript/base.json`
- `packages/config-typescript/expo.json`
- `packages/config-typescript/next.json`
- `packages/config-eslint/package.json`
- `packages/config-eslint/base.cjs`
- `packages/config-eslint/expo.cjs`
- `packages/config-eslint/next.cjs`
- `infra/README.md`
- `infra/local/`
- `infra/deploy/`
- `docs/README.md`
- `docs/adr/`
- `docs/setup/`
- `scripts/README.md`
- `scripts/api/dev.sh`
- `scripts/api/lint.sh`
- `scripts/api/typecheck.sh`
- `scripts/api/test.sh`
- `scripts/api/format.sh`

## Architecture constraints

- `apps/api` stays a Python project and is excluded from `pnpm-workspace.yaml`
- `packages/` may hold JS/TS config and generated contracts, not backend business logic
- FastAPI remains the single source of backend business logic and API contracts
- Supabase is not part of this phase
- Phase 00 must not scaffold the apps
- Phase 00 must not include product-domain implementation
- no shared UI package
- no catch-all shared package

## Definition of done

- the repo skeleton matches the agreed ownership model
- root tooling files are present
- the two initial config packages exist
- root script names are defined
- Python API orchestration is documented via `scripts/api/`
- `README.md` explains prerequisites, layout, and command names
- workspace install behavior is deterministic and explicit
- no app scaffolds or product implementation were added

## Validation/checks to run

- `pnpm install`
- `pnpm exec turbo run lint --dry`
- `pnpm exec turbo run typecheck --dry`
- `pnpm exec turbo run test --dry`
- `pnpm exec turbo run format --dry`
- verify `pnpm-workspace.yaml` includes only JS/TS workspaces
- verify `apps/api` is excluded from the JS workspace model
- verify root script names exist in `package.json`
- verify `.npmrc` enforces exact versions and explicit workspace behavior
- verify `README.md` documents Node, pnpm, Python, uv, Docker, and Docker Compose
