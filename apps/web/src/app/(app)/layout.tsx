import type { ReactNode } from "react";

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
          <p className="eyebrow">Protected Shell</p>
          <h1 className="app-title">Tenue Auth Foundation</h1>
        </div>

        <div className="app-header-actions">
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
