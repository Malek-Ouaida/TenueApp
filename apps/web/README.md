# apps/web

Next.js + TypeScript app scaffold for Tenue.

Phase 03 adds the first real web slice:

- `/login` and `/register` auth pages
- API-backed server actions for register/login/logout
- `HttpOnly` cookie session orchestration
- a protected shell at `/`

Still out of scope:

- closet or any product-domain pages
- direct Supabase Auth integration in the browser
