"use client";

import Link from "next/link";
import { useActionState } from "react";

import { initialAuthFormState, loginAction } from "../../actions/auth";

export default function LoginPage() {
  const [state, formAction, isPending] = useActionState(loginAction, initialAuthFormState);

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">Phase 3.3</p>
        <h1 className="headline auth-headline">Sign in to Tenue</h1>
        <p className="body-copy auth-copy">
          Web stays a real secondary surface, but auth still resolves through the same API-owned
          contract.
        </p>

        <form action={formAction} className="auth-form">
          <label className="auth-label" htmlFor="email">
            Email
          </label>
          <input className="auth-input" id="email" name="email" type="email" required />

          <label className="auth-label" htmlFor="password">
            Password
          </label>
          <input className="auth-input" id="password" name="password" type="password" required />

          {state.error ? <p className="auth-error">{state.error}</p> : null}

          <button className="auth-button" type="submit" disabled={isPending}>
            {isPending ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="auth-footnote">
          New here? <Link href="/register">Create an account</Link>
        </p>
      </section>
    </main>
  );
}
