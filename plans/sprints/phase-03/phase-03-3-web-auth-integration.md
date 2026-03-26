# Phase 03.3 -- Web auth integration

## Goal

Integrate Next.js web auth flows against the finished API contract.

## Scope

- create login and register pages
- use server actions for auth submissions
- persist access and refresh tokens in `HttpOnly` cookies
- resolve protected user scope on the server
- refresh the session on protected page loads when needed
- support logout and protected-shell rendering

## Deliverables

- `/login`
- `/register`
- protected shell at `/`
- cookie/session helpers
- server-side `me` resolution for protected pages

## Acceptance

- register works
- login works
- reloading `/` preserves access through cookie-backed session handling
- logout clears the cookies and returns to login
