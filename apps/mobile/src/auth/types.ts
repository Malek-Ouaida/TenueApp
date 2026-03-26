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

export type AuthMeResponse = {
  user: AuthUser;
};

export type AuthStatus = "loading" | "anonymous" | "authenticated";

export type AuthResult =
  | {
      ok: true;
    }
  | {
      ok: false;
      error: string;
    };
