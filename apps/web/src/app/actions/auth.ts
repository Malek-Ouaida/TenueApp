"use server";

import { redirect } from "next/navigation";

import { apiRequest, ApiError } from "../../lib/api";
import { clearAuthCookies, writeAuthCookies } from "../../lib/auth/cookies";
import { logoutCurrentSession, type AuthSessionResponse } from "../../lib/auth/session";

export type AuthFormState = {
  error: string | null;
};

export const initialAuthFormState: AuthFormState = {
  error: null
};

export async function loginAction(
  _: AuthFormState,
  formData: FormData
): Promise<AuthFormState> {
  return submitCredentials("/auth/login", formData);
}

export async function registerAction(
  _: AuthFormState,
  formData: FormData
): Promise<AuthFormState> {
  return submitCredentials("/auth/register", formData);
}

export async function logoutAction() {
  await logoutCurrentSession();
  await clearAuthCookies();
  redirect("/login");
}

async function submitCredentials(
  endpoint: "/auth/login" | "/auth/register",
  formData: FormData
): Promise<AuthFormState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  try {
    const response = await apiRequest<AuthSessionResponse>(endpoint, {
      method: "POST",
      json: {
        email,
        password
      }
    });

    await writeAuthCookies({
      accessToken: response.session.access_token,
      refreshToken: response.session.refresh_token
    });
  } catch (error) {
    return {
      error: error instanceof ApiError ? error.message : "Authentication failed."
    };
  }

  redirect("/");
}
