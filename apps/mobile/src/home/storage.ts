import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const homeFtueKey = "tenue.home.ftue";

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

async function readValue(): Promise<string | null> {
  const browserStorage = getBrowserStorage();

  if (browserStorage) {
    try {
      return browserStorage.getItem(homeFtueKey);
    } catch {
      return null;
    }
  }

  return SecureStore.getItemAsync(homeFtueKey);
}

async function writeValue(value: string): Promise<void> {
  const browserStorage = getBrowserStorage();

  if (browserStorage) {
    try {
      browserStorage.setItem(homeFtueKey, value);
    } catch {
      // Ignore browser persistence failures and let the UI continue.
    }
    return;
  }

  await SecureStore.setItemAsync(homeFtueKey, value);
}

export async function hasSeenHomeFtue(): Promise<boolean> {
  return (await readValue()) === "seen";
}

export async function markHomeFtueSeen(): Promise<void> {
  await writeValue("seen");
}
