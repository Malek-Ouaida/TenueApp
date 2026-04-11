import Constants from "expo-constants";
import { Platform } from "react-native";

const fallbackLocalApiHost = Platform.OS === "android" ? "10.0.2.2" : "127.0.0.1";
const fallbackApiBaseUrl = `http://${fallbackLocalApiHost}:8000`;

function normalizeLocalHost(host: string | null): string | null {
  if (!host) {
    return null;
  }

  const normalized = host.trim().replace(/^\[|\]$/g, "");
  if (!normalized) {
    return null;
  }

  if (Platform.OS === "android" && (normalized === "localhost" || normalized === "127.0.0.1")) {
    return "10.0.2.2";
  }

  return normalized;
}

function extractHost(candidate: string | null | undefined): string | null {
  const normalized = candidate?.trim();
  if (!normalized) {
    return null;
  }

  const withScheme = normalized.includes("://") ? normalized : `http://${normalized}`;

  try {
    return normalizeLocalHost(new URL(withScheme).hostname);
  } catch {
    return null;
  }
}

function getExpoDevServerHost(): string | null {
  const platformHostUri =
    Constants.platform && typeof Constants.platform === "object" && "hostUri" in Constants.platform
      ? String((Constants.platform as { hostUri?: string }).hostUri ?? "")
      : null;

  const candidates = [
    Constants.expoConfig?.hostUri,
    platformHostUri,
    Constants.experienceUrl,
    Constants.linkingUri
  ];

  for (const candidate of candidates) {
    const host = extractHost(candidate);
    if (host) {
      return host;
    }
  }

  return null;
}

function getDefaultApiBaseUrl(): string {
  const configuredApiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (configuredApiBaseUrl) {
    return configuredApiBaseUrl;
  }

  const expoDevServerHost = getExpoDevServerHost();
  if (expoDevServerHost) {
    return `http://${expoDevServerHost}:8000`;
  }

  return fallbackApiBaseUrl;
}

export const apiBaseUrl = getDefaultApiBaseUrl().replace(/\/$/, "");
