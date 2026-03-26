import {
  startTransition,
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode
} from "react";

import { ApiError } from "../lib/api";
import { getMe, login, logout, refreshSession, register } from "./client";
import { clearStoredSession, loadStoredSession, persistStoredSession } from "./storage";
import type {
  AuthResult,
  AuthRegistrationResponse,
  AuthSession,
  AuthStatus,
  AuthUser
} from "./types";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  session: AuthSession | null;
  loginWithPassword: (email: string, password: string) => Promise<AuthResult>;
  registerWithPassword: (email: string, password: string) => Promise<AuthResult>;
  logoutCurrentUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [session, setSession] = useState<AuthSession | null>(null);

  useEffect(() => {
    let mounted = true;

    async function hydrateSession() {
      const storedSession = await loadStoredSession();

      if (!storedSession) {
        if (!mounted) {
          return;
        }

        startTransition(() => {
          setUser(null);
          setSession(null);
          setStatus("anonymous");
        });
        return;
      }

      try {
        const meResponse = await getMe(storedSession.access_token);
        if (!mounted) {
          return;
        }

        startTransition(() => {
          setUser(meResponse.user);
          setSession(storedSession);
          setStatus("authenticated");
        });
        return;
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) {
          await clearStoredSession();
          if (!mounted) {
            return;
          }

          startTransition(() => {
            setUser(null);
            setSession(null);
            setStatus("anonymous");
          });
          return;
        }
      }

      try {
        const refreshedSession = await refreshSession(storedSession.refresh_token);
        await persistStoredSession(refreshedSession.session);

        if (!mounted) {
          return;
        }

        startTransition(() => {
          setUser(refreshedSession.user);
          setSession(refreshedSession.session);
          setStatus("authenticated");
        });
      } catch {
        await clearStoredSession();
        if (!mounted) {
          return;
        }

        startTransition(() => {
          setUser(null);
          setSession(null);
          setStatus("anonymous");
        });
      }
    }

    void hydrateSession();

    return () => {
      mounted = false;
    };
  }, []);

  async function authenticate(
    executor: () => Promise<{ user: AuthUser; session: AuthSession }>
  ): Promise<AuthResult> {
    try {
      const response = await executor();
      await persistStoredSession(response.session);

      startTransition(() => {
        setUser(response.user);
        setSession(response.session);
        setStatus("authenticated");
      });

      return { ok: true, nextStep: "authenticated" };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Authentication failed.";
      return {
        ok: false,
        error: message
      };
    }
  }

  async function loginWithPassword(email: string, password: string): Promise<AuthResult> {
    return authenticate(() => login({ email, password }));
  }

  async function registerWithPassword(email: string, password: string): Promise<AuthResult> {
    try {
      const response: AuthRegistrationResponse = await register({ email, password });

      if (response.session) {
        await persistStoredSession(response.session);
        startTransition(() => {
          setUser(response.user);
          setSession(response.session);
          setStatus("authenticated");
        });

        return { ok: true, nextStep: "authenticated" };
      }

      startTransition(() => {
        setUser(null);
        setSession(null);
        setStatus("anonymous");
      });

      return {
        ok: true,
        nextStep: "verify_email",
        message: "Check your email to verify your account, then sign in."
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Authentication failed.";
      return {
        ok: false,
        error: message
      };
    }
  }

  async function logoutCurrentUser(): Promise<void> {
    const currentSession = session;

    try {
      if (currentSession) {
        await logout(currentSession.access_token);
      }
    } catch {
      // Logging out locally is the safe fallback if the upstream session is already gone.
    } finally {
      await clearStoredSession();
      startTransition(() => {
        setUser(null);
        setSession(null);
        setStatus("anonymous");
      });
    }
  }

  const value: AuthContextValue = {
    status,
    user,
    session,
    loginWithPassword,
    registerWithPassword,
    logoutCurrentUser
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside an AuthProvider.");
  }

  return context;
}
