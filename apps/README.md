# Apps

This directory contains deployable product surfaces only.

- `mobile/`: Expo + React Native app
- `web/`: Next.js app
- `api/`: FastAPI backend

Rules:

- app-local runtime code belongs inside the app that owns it
- shared backend business logic does not belong here or in `packages/`
- `apps/api` remains a Python project outside the pnpm workspace model
- app scaffolding begins in Phase 01, not Phase 00
