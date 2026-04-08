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
  ttlSeconds?: number;
};

export type CursorPageResponse<T> = {
  items: T[];
  next_cursor: string | null;
};

type ErrorPayload = {
  detail?: string;
};

type CachedResponseEntry = {
  expiresAt: number;
  promise: Promise<unknown>;
};

const responseCache = new Map<string, CachedResponseEntry>();
const maxResponseCacheEntries = 500;

function getApiBaseUrl() {
  return (process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? defaultApiBaseUrl).replace(
    /\/$/,
    ""
  );
}

export function buildApiPath(
  path: string,
  query: Record<string, string | number | boolean | null | undefined> = {}
) {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }

    searchParams.set(key, String(value));
  }

  const search = searchParams.toString();
  return search ? `${path}?${search}` : path;
}

export async function fetchAllCursorPages<T>(
  fetchPage: (cursor: string | null) => Promise<CursorPageResponse<T>>,
  options: { maxPages?: number } = {}
) {
  const maxPages = options.maxPages ?? 20;
  const items: T[] = [];
  let cursor: string | null = null;

  for (let page = 0; page < maxPages; page += 1) {
    const response = await fetchPage(cursor);
    items.push(...response.items);

    if (!response.next_cursor) {
      return items;
    }

    cursor = response.next_cursor;
  }

  return items;
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

  const method = options.method ?? "GET";
  const requestUrl = `${getApiBaseUrl()}${path}`;
  const ttlMs = (options.ttlSeconds ?? 0) * 1000;
  const authorization = headers.get("Authorization") ?? "";

  const executeRequest = async () => {
    const response = await fetch(requestUrl, {
      method,
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : undefined,
      cache: "no-store"
    });

    if (!response.ok) {
      let detail = "Request failed.";
      const responseText = await response.text();

      try {
        const payload = JSON.parse(responseText) as ErrorPayload;
        if (payload.detail) {
          detail = payload.detail;
        }
      } catch {
        const trimmed = responseText.trim();
        detail = trimmed ? trimmed : "Request failed.";
      }

      throw new ApiError(detail, response.status);
    }

    return (await response.json()) as T;
  };

  if (method === "GET" && options.json === undefined && ttlMs > 0) {
    const now = Date.now();
    const cacheKey = `${method} ${requestUrl} ${authorization}`;
    const cached = responseCache.get(cacheKey);

    if (cached && cached.expiresAt > now) {
      return cached.promise as Promise<T>;
    }

    if (responseCache.size >= maxResponseCacheEntries) {
      for (const [key, entry] of responseCache.entries()) {
        if (entry.expiresAt <= now) {
          responseCache.delete(key);
        }
      }
      if (responseCache.size >= maxResponseCacheEntries) {
        responseCache.delete(responseCache.keys().next().value as string);
      }
    }

    const promise = executeRequest().catch((error) => {
      const current = responseCache.get(cacheKey);
      if (current?.promise === promise) {
        responseCache.delete(cacheKey);
      }
      throw error;
    });

    responseCache.set(cacheKey, {
      expiresAt: now + ttlMs,
      promise
    });

    return promise;
  }

  return executeRequest();
}
