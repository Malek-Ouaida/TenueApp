import { apiBaseUrl } from "./config";

type ApiRequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
};

type ErrorPayload = {
  detail?: string | { code?: string; message?: string };
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...options.headers
  };

  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;

  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined
    });
  } catch {
    throw new ApiError(
      `Could not reach the Tenue API at ${apiBaseUrl}. Start the backend or set EXPO_PUBLIC_API_BASE_URL.`,
      0,
      "network_error"
    );
  }

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    let code: string | undefined;
    const responseText = await response.text();

    try {
      const payload = JSON.parse(responseText) as ErrorPayload;
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (payload.detail?.message) {
        message = payload.detail.message;
        code = payload.detail.code;
      }
    } catch {
      const trimmed = responseText.trim();
      if (trimmed && !trimmed.startsWith("<")) {
        message = trimmed;
      }
    }

    throw new ApiError(message, response.status, code);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
