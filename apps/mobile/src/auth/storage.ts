import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

import type { AuthSession } from "./types";

const authSessionKey = "tenue.auth.session";

type BrowserStorageHost = typeof globalThis & {
  localStorage?: Storage;
};

function getBrowserStorage(): Storage | null {
  if (Platform.OS !== "web") {
    return null;
  }

  const host = globalThis as BrowserStorageHost;
  return host.localStorage ?? null;
}

async function getStoredValue(): Promise<string | null> {
  const browserStorage = getBrowserStorage();
  if (browserStorage) {
    try {
      return browserStorage.getItem(authSessionKey);
    } catch {
      return null;
    }
  }

  return SecureStore.getItemAsync(authSessionKey);
}

async function setStoredValue(value: string): Promise<void> {
  const browserStorage = getBrowserStorage();
  if (browserStorage) {
    try {
      browserStorage.setItem(authSessionKey, value);
    } catch {
      // Ignore browser storage errors and let auth continue without persistence.
    }
    return;
  }

  await SecureStore.setItemAsync(authSessionKey, value);
}

async function removeStoredValue(): Promise<void> {
  const browserStorage = getBrowserStorage();
  if (browserStorage) {
    try {
      browserStorage.removeItem(authSessionKey);
    } catch {
      // Ignore browser storage errors and let auth continue without persistence.
    }
    return;
  }

  await SecureStore.deleteItemAsync(authSessionKey);
}

export async function loadStoredSession(): Promise<AuthSession | null> {
  const rawValue = await getStoredValue();
  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as AuthSession;
  } catch {
    await removeStoredValue();
    return null;
  }
}

export async function persistStoredSession(session: AuthSession): Promise<void> {
  await setStoredValue(JSON.stringify(session));
}

export async function clearStoredSession(): Promise<void> {
  await removeStoredValue();
}
