const defaultApiBaseUrl = "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiRequestOptions = {
  method?: string;
  json?: unknown;
  headers?: HeadersInit;
};

type ErrorPayload = {
  detail?: string;
};

function getApiBaseUrl() {
  return (process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? defaultApiBaseUrl).replace(
    /\/$/,
    ""
  );
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.json !== undefined ? JSON.stringify(options.json) : undefined,
    cache: "no-store"
  });

  if (!response.ok) {
    let detail = "Request failed.";

    try {
      const payload = (await response.json()) as ErrorPayload;
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      detail = "Request failed.";
    }

    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}
