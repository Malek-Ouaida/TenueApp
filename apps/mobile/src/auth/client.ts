import { apiRequest } from "../lib/api";
import type { AuthMeResponse, AuthRegistrationResponse, AuthSessionResponse } from "./types";

type Credentials = {
  email: string;
  password: string;
};

export function register(credentials: Credentials): Promise<AuthRegistrationResponse> {
  return apiRequest<AuthRegistrationResponse>("/auth/register", {
    method: "POST",
    body: credentials
  });
}

export function login(credentials: Credentials): Promise<AuthSessionResponse> {
  return apiRequest<AuthSessionResponse>("/auth/login", {
    method: "POST",
    body: credentials
  });
}

export function refreshSession(refreshToken: string): Promise<AuthSessionResponse> {
  return apiRequest<AuthSessionResponse>("/auth/refresh", {
    method: "POST",
    body: {
      refresh_token: refreshToken
    }
  });
}

export function logout(accessToken: string): Promise<{ success: boolean }> {
  return apiRequest<{ success: boolean }>("/auth/logout", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`
    }
  });
}

export function getMe(accessToken: string): Promise<AuthMeResponse> {
  return apiRequest<AuthMeResponse>("/auth/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`
    }
  });
}
