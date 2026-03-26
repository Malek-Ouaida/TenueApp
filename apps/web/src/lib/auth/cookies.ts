import { cookies } from "next/headers";

type SessionCookiePayload = {
  accessToken: string;
  refreshToken: string;
};

const accessTokenCookieName = "tenue_access_token";
const refreshTokenCookieName = "tenue_refresh_token";
const cookieMaxAgeSeconds = 60 * 60 * 24 * 30;

function shouldUseSecureCookies() {
  return process.env.AUTH_COOKIE_SECURE === "true" || process.env.NODE_ENV === "production";
}

export async function readAuthCookies(): Promise<SessionCookiePayload> {
  const cookieStore = await cookies();

  return {
    accessToken: cookieStore.get(accessTokenCookieName)?.value ?? "",
    refreshToken: cookieStore.get(refreshTokenCookieName)?.value ?? ""
  };
}

export async function writeAuthCookies(payload: SessionCookiePayload): Promise<void> {
  const cookieStore = await cookies();
  const baseCookieOptions = {
    httpOnly: true,
    maxAge: cookieMaxAgeSeconds,
    path: "/",
    sameSite: "lax" as const,
    secure: shouldUseSecureCookies()
  };

  cookieStore.set(accessTokenCookieName, payload.accessToken, baseCookieOptions);
  cookieStore.set(refreshTokenCookieName, payload.refreshToken, baseCookieOptions);
}

export async function clearAuthCookies(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(accessTokenCookieName);
  cookieStore.delete(refreshTokenCookieName);
}
