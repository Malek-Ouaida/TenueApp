import { NextResponse, type NextRequest } from "next/server";

import { apiRequest } from "@/lib/api";
import type { AuthSessionResponse } from "@/lib/auth/session";
import { clearAuthCookies, readAuthCookies, writeAuthCookies } from "@/lib/auth/cookies";

export async function GET(request: NextRequest) {
  const redirectPath = resolveRedirectPath(request.nextUrl.searchParams.get("redirect"), "/dashboard");
  const fallbackPath = resolveRedirectPath(request.nextUrl.searchParams.get("fallback"), "/signin");
  const { refreshToken } = await readAuthCookies();

  if (!refreshToken) {
    await clearAuthCookies();
    return NextResponse.redirect(new URL(fallbackPath, request.url));
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

    return NextResponse.redirect(new URL(redirectPath, request.url));
  } catch {
    await clearAuthCookies();
    return NextResponse.redirect(new URL(fallbackPath, request.url));
  }
}

function resolveRedirectPath(candidate: string | null, fallback: string) {
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//")) {
    return fallback;
  }

  return candidate;
}
