# Phase 03.2 -- Mobile auth integration

## Goal

Integrate Expo mobile auth flows against the finished API contract.

## Scope

- create register and login screens
- add an API-backed auth provider state layer
- persist the session in secure local storage
- hydrate the session when the app starts
- add a protected authenticated shell
- support logout and expired-session fallback

## Deliverables

- unauthenticated auth screens
- protected shell route
- session hydration on launch
- logout behavior that clears local state safely

## Acceptance

- register works
- login works
- relaunch restores the session
- authenticated users land in the protected shell
- logout clears the session and returns to login
