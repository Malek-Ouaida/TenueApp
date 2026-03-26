"use client";

import { useActionState } from "react";

import { initialProfileFormState, updateProfileAction } from "../../app/actions/profile";
import type { Profile } from "../../lib/profile";

type ProfilePageProps = {
  email: string;
  profile: Profile;
  saved: boolean;
};

export function ProfilePage({ email, profile, saved }: ProfilePageProps) {
  const [state, formAction, isPending] = useActionState(
    updateProfileAction,
    initialProfileFormState
  );

  const displayName = profile.display_name ?? "Add a display name";
  const usernameLabel = profile.username ? `@${profile.username}` : "Claim your username";
  const bio =
    profile.bio ??
    "This shell is ready for your identity now, and for lookbook and stats surfaces later.";
  const initials = getInitials(profile, email);

  return (
    <div className="profile-shell">
      <section className="profile-hero">
        <div className="profile-avatar-frame">
          {profile.avatar_url ? (
            <div
              aria-label={`${displayName} avatar`}
              className="profile-avatar-image"
              role="img"
              style={{ backgroundImage: `url(${profile.avatar_url})` }}
            />
          ) : (
            <span className="profile-avatar-fallback">{initials}</span>
          )}
        </div>

        <div className="profile-hero-copy">
          <div className="profile-hero-topline">
            <p className="panel-kicker">Profile Foundation</p>
            <span className="profile-badge">Private shell</span>
          </div>

          <h1 className="profile-handle">{usernameLabel}</h1>
          <p className="profile-display-name">{displayName}</p>
          <p className="profile-bio-copy">{bio}</p>

          <div className="profile-meta-row">
            <span className="profile-meta-pill">{email}</span>
            <span className="profile-meta-pill">
              {profile.username ? `/u/${profile.username}` : "Future route unlocks after username claim"}
            </span>
            <span className="profile-meta-pill">Lookbook and stats stay placeholder-only</span>
          </div>
        </div>
      </section>

      <section className="profile-grid-layout">
        <article className="profile-panel profile-panel-form">
          <div className="profile-panel-header">
            <div>
              <p className="panel-kicker">Edit Identity</p>
              <h2 className="profile-panel-title">Own the profile shell</h2>
            </div>
            <span className="profile-panel-helper">Backend validation stays canonical</span>
          </div>

          <form action={formAction} className="profile-form">
            <label className="auth-label" htmlFor="username">
              Username
            </label>
            <input
              className="auth-input"
              defaultValue={profile.username ?? ""}
              id="username"
              name="username"
              placeholder="closet.coded"
            />

            <p className="profile-field-note">
              Lowercase letters, numbers, periods, and underscores only.
            </p>

            <label className="auth-label" htmlFor="displayName">
              Display name
            </label>
            <input
              className="auth-input"
              defaultValue={profile.display_name ?? ""}
              id="displayName"
              name="displayName"
              placeholder="Malek Ouaida"
            />

            <label className="auth-label" htmlFor="bio">
              Bio
            </label>
            <textarea
              className="auth-input profile-textarea"
              defaultValue={profile.bio ?? ""}
              id="bio"
              name="bio"
              placeholder="Building a sharper wardrobe system."
              rows={4}
            />

            {state.error ? <p className="auth-error">{state.error}</p> : null}
            {saved ? <p className="auth-notice">Profile saved.</p> : null}

            <button className="auth-button" type="submit" disabled={isPending}>
              {isPending ? "Saving…" : "Save profile"}
            </button>
          </form>
        </article>

        <article className="profile-panel">
          <div className="profile-panel-header">
            <div>
              <p className="panel-kicker">Profile Surface</p>
              <h2 className="profile-panel-title">Header first, content later</h2>
            </div>
          </div>

          <p className="panel-copy">
            This phase establishes the identity shell only. Future lookbook, insights, and wardrobe
            sections will plug into this grid without changing the route structure.
          </p>

          <div className="profile-placeholder-stack">
            <div className="profile-placeholder-card">
              <span className="profile-placeholder-title">Lookbook</span>
              <span className="profile-placeholder-copy">Pinned for future outfit logs and visual history.</span>
            </div>
            <div className="profile-placeholder-card">
              <span className="profile-placeholder-title">Stats</span>
              <span className="profile-placeholder-copy">Reserved for wear data, streaks, and closet insights.</span>
            </div>
          </div>
        </article>

        <article className="profile-mosaic">
          <div className="profile-mosaic-header">
            <p className="panel-kicker">Grid Preview</p>
            <h2 className="profile-panel-title">Prepared for image-led sections</h2>
          </div>

          <div className="profile-mosaic-grid">
            <div className="profile-mosaic-tile profile-mosaic-tile-large">
              <span>Hero lookbook slot</span>
            </div>
            <div className="profile-mosaic-tile">
              <span>Closet stats</span>
            </div>
            <div className="profile-mosaic-tile">
              <span>Saved looks</span>
            </div>
            <div className="profile-mosaic-tile">
              <span>Insights</span>
            </div>
            <div className="profile-mosaic-tile">
              <span>Recent activity</span>
            </div>
          </div>
        </article>
      </section>
    </div>
  );
}

function getInitials(profile: Profile, email: string): string {
  const source = profile.display_name ?? profile.username ?? email;

  return source
    .split(/[\s._@-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0]?.toUpperCase() ?? "")
    .join("") || "T";
}
