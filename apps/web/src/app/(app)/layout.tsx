import type { ReactNode } from "react";
import Link from "next/link";

import { logoutAction } from "../actions/auth";
import { requireSession } from "../../lib/auth/session";

type AppLayoutProps = {
  children: ReactNode;
};

export default async function AppLayout({ children }: AppLayoutProps) {
  const session = await requireSession();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Tenue</p>
          <Link className="app-title-link" href="/profile">
            <h1 className="app-title">Profile Identity</h1>
          </Link>
        </div>

        <div className="app-header-actions">
          <Link className="ghost-link" href="/profile">
            My profile
          </Link>
          <span className="app-user-chip">{session.user.email}</span>
          <form action={logoutAction}>
            <button className="ghost-button" type="submit">
              Sign out
            </button>
          </form>
        </div>
      </header>

      <main className="app-content">{children}</main>
    </div>
  );
}
