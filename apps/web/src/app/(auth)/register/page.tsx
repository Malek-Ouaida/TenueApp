"use client";

import Link from "next/link";
import { useActionState } from "react";

import { initialAuthFormState, registerAction } from "../../actions/auth";

export default function RegisterPage() {
  const [state, formAction, isPending] = useActionState(registerAction, initialAuthFormState);

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">Phase 3.3</p>
        <h1 className="headline auth-headline">Create your account</h1>
        <p className="body-copy auth-copy">
          This phase only establishes identity, session handling, and a protected user scope.
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
            {isPending ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="auth-footnote">
          Already registered? <Link href="/login">Sign in</Link>
        </p>
      </section>
    </main>
  );
}
