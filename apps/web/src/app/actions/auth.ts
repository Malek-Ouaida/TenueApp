"use server";

import { redirect } from "next/navigation";

import type { AuthFormState } from "../(auth)/form-state";
import { apiRequest, ApiError } from "../../lib/api";
import { clearAuthCookies, writeAuthCookies } from "../../lib/auth/cookies";
import {
  logoutCurrentSession,
  type AuthRegistrationResponse,
  type AuthSessionResponse
} from "../../lib/auth/session";

export async function loginAction(
  _: AuthFormState,
  formData: FormData
): Promise<AuthFormState> {
  return submitLoginCredentials(formData);
}

export async function registerAction(
  _: AuthFormState,
  formData: FormData
): Promise<AuthFormState> {
  return submitRegistration(formData);
}

export async function logoutAction() {
  await logoutCurrentSession();
  await clearAuthCookies();
  redirect("/login");
}

async function submitLoginCredentials(formData: FormData): Promise<AuthFormState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  try {
    const response = await apiRequest<AuthSessionResponse>("/auth/login", {
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
      error: error instanceof ApiError ? error.message : "Authentication failed.",
      notice: null
    };
  }

  redirect("/profile");
}

async function submitRegistration(formData: FormData): Promise<AuthFormState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  try {
    const response = await apiRequest<AuthRegistrationResponse>("/auth/register", {
      method: "POST",
      json: {
        email,
        password
      }
    });

    if (response.session) {
      await writeAuthCookies({
        accessToken: response.session.access_token,
        refreshToken: response.session.refresh_token
      });
      redirect("/profile");
    }

    return {
      error: null,
      notice: "Check your email to verify your account, then sign in."
    };
  } catch (error) {
    return {
      error: error instanceof ApiError ? error.message : "Authentication failed.",
      notice: null
    };
  }
}
