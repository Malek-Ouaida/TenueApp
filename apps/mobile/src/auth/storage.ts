import * as SecureStore from "expo-secure-store";

import type { AuthSession } from "./types";

const authSessionKey = "tenue.auth.session";

export async function loadStoredSession(): Promise<AuthSession | null> {
  const rawValue = await SecureStore.getItemAsync(authSessionKey);
  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as AuthSession;
  } catch {
    await SecureStore.deleteItemAsync(authSessionKey);
    return null;
  }
}

export function persistStoredSession(session: AuthSession): Promise<void> {
  return SecureStore.setItemAsync(authSessionKey, JSON.stringify(session));
}

export function clearStoredSession(): Promise<void> {
  return SecureStore.deleteItemAsync(authSessionKey);
}
