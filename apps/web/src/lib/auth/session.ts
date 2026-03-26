import { redirect } from "next/navigation";

import { apiRequest, ApiError } from "../api";
import { clearAuthCookies, readAuthCookies, writeAuthCookies } from "./cookies";

export type AuthUser = {
  id: string;
  email: string;
  auth_provider: string;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
};

export type AuthSession = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  expires_at: string | null;
};

export type AuthSessionResponse = {
  user: AuthUser;
  session: AuthSession;
};

export type AuthRegistrationResponse = {
  user: AuthUser;
  session: AuthSession | null;
  email_verification_required: boolean;
};

type MeResponse = {
  user: AuthUser;
};

export async function resolveSession(): Promise<AuthSessionResponse | null> {
  const { accessToken, refreshToken } = await readAuthCookies();
  if (!accessToken || !refreshToken) {
    return null;
  }

  try {
    const me = await apiRequest<MeResponse>("/auth/me", {
      headers: {
        Authorization: `Bearer ${accessToken}`
      }
    });

    return {
      user: me.user,
      session: {
        access_token: accessToken,
        refresh_token: refreshToken,
        token_type: "bearer",
        expires_in: 0,
        expires_at: null
      }
    };
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) {
      await clearAuthCookies();
      return null;
    }
  }

  try {
    const refreshed = await apiRequest<AuthSessionResponse>("/auth/refresh", {
      method: "POST",
      json: {
        refresh_token: refreshToken
      }
    });

    await writeAuthCookies({
      accessToken: refreshed.session.access_token,
      refreshToken: refreshed.session.refresh_token
    });

    return refreshed;
  } catch {
    await clearAuthCookies();
    return null;
  }
}

export async function requireSession(): Promise<AuthSessionResponse> {
  const session = await resolveSession();
  if (!session) {
    redirect("/login");
  }

  return session;
}

export async function logoutCurrentSession(): Promise<void> {
  const { accessToken } = await readAuthCookies();

  try {
    if (accessToken) {
      await apiRequest<{ success: boolean }>("/auth/logout", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`
        }
      });
    }
  } catch {
    // Local cookie clearing is still the correct fallback for expired or missing sessions.
  } finally {
    await clearAuthCookies();
  }
}
