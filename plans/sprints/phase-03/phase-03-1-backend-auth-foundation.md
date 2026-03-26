# Phase 03.1 -- Backend auth foundation

## Goal

Ship the backend auth slice and the stable contract that both clients consume.

## Scope

- create the `users` table
- add the `auth` domain with provider adapter, repository, and service
- expose register, login, refresh, logout, and `me`
- add the protected-user dependency
- document API auth env requirements
- cover the auth slice with API tests

## Deliverables

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- reusable current-user dependency
- Alembic migration for the app-owned `users` table
- API tests for success and failure paths

## Acceptance

- backend auth tests pass
- the API contract is stable enough for mobile and web to integrate without inventing auth behavior
