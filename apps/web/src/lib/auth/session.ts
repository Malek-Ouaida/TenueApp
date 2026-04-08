import { redirect } from "next/navigation";

import { apiRequest, ApiError } from "../api";
import { clearAuthCookies, readAuthCookies } from "./cookies";

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

export type SessionResolution =
  | {
      status: "authenticated";
      value: AuthSessionResponse;
    }
  | {
      status: "missing";
    }
  | {
      status: "refresh-required";
    }
  | {
      status: "unavailable";
    };

const sessionRecoveryPath = "/auth/session/recover?redirect=%2Fdashboard&fallback=%2Fsignin";

export function getSessionRecoveryPath() {
  return sessionRecoveryPath;
}

export async function resolveSession(): Promise<SessionResolution> {
  const { accessToken, refreshToken } = await readAuthCookies();
  if (!accessToken || !refreshToken) {
    return {
      status: "missing"
    };
  }

  try {
    const me = await apiRequest<MeResponse>("/auth/me", {
      headers: {
        Authorization: `Bearer ${accessToken}`
      },
      ttlSeconds: 10
    });

    return {
      status: "authenticated",
      value: {
        user: me.user,
        session: {
          access_token: accessToken,
          refresh_token: refreshToken,
          token_type: "bearer",
          expires_in: 0,
          expires_at: null
        }
      }
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return {
        status: "refresh-required"
      };
    }

    return {
      status: "unavailable"
    };
  }
}

export async function requireSession(): Promise<AuthSessionResponse> {
  const resolution = await resolveSession();
  if (resolution.status === "authenticated") {
    return resolution.value;
  }

  if (resolution.status === "refresh-required") {
    redirect(sessionRecoveryPath);
  }

  redirect("/signin");
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
