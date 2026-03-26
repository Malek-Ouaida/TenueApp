export default async function ProtectedHomePage() {
  return (
    <section className="app-card-grid">
      <article className="app-panel">
        <p className="panel-kicker">Authenticated Identity</p>
        <h2 className="panel-title">`GET /auth/me` is now the shared user scope.</h2>
        <p className="panel-copy">
          The authenticated shell is intentionally small: email, session continuity, and logout.
        </p>
      </article>

      <article className="app-panel accent-panel">
        <p className="panel-kicker">Current User</p>
        <h2 className="panel-title">Resolved on the server</h2>
        <p className="panel-copy">
          This page is rendered only after the web app resolves auth through the API contract.
        </p>
      </article>
    </section>
  );
}
