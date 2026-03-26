import Constants from "expo-constants";

const fallbackApiBaseUrl = "http://127.0.0.1:8000";

function getExpoDevServerHost(): string | null {
  const hostUri = Constants.expoConfig?.hostUri?.trim();
  if (!hostUri) {
    return null;
  }

  const [host] = hostUri.split(":");
  return host || null;
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
