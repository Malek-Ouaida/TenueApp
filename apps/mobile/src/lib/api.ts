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

  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined
  });

  if (!response.ok) {
    let message = "Request failed.";
    let code: string | undefined;

    try {
      const payload = (await response.json()) as ErrorPayload;
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (payload.detail?.message) {
        message = payload.detail.message;
        code = payload.detail.code;
      }
    } catch {
      message = "Request failed.";
    }

    throw new ApiError(message, response.status, code);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
