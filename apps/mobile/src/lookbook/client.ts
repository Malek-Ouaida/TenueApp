import { apiRequest } from "../lib/api";
import type { WearLogDetailSnapshot } from "../wear/types";
import type {
  LookbookEntryCreateRequest,
  LookbookEntryDetailSnapshot,
  LookbookEntryFilters,
  LookbookEntryListResponse,
  LookbookEntryUpdateRequest,
  LookbookUploadIntentRequest,
  LookbookUploadIntentResponse,
  LookbookWearLogCreateRequest,
  PrivateImageSnapshot
} from "./types";

function buildAuthHeaders(accessToken: string, extraHeaders?: Record<string, string>) {
  return {
    Authorization: `Bearer ${accessToken}`,
    ...extraHeaders
  };
}

function buildQueryString(params: Record<string, string | number | boolean | null | undefined>) {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") {
      continue;
    }

    searchParams.set(key, String(value));
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export function getLookbookEntries(accessToken: string, filters: LookbookEntryFilters = {}) {
  return apiRequest<LookbookEntryListResponse>(`/lookbook/entries${buildQueryString(filters)}`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function getLookbookEntry(accessToken: string, entryId: string) {
  return apiRequest<LookbookEntryDetailSnapshot>(`/lookbook/entries/${entryId}`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function createLookbookEntry(accessToken: string, payload: LookbookEntryCreateRequest) {
  return apiRequest<LookbookEntryDetailSnapshot>("/lookbook/entries", {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function updateLookbookEntry(
  accessToken: string,
  entryId: string,
  payload: LookbookEntryUpdateRequest
) {
  return apiRequest<LookbookEntryDetailSnapshot>(`/lookbook/entries/${entryId}`, {
    method: "PATCH",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function archiveLookbookEntry(accessToken: string, entryId: string) {
  return apiRequest<void>(`/lookbook/entries/${entryId}/archive`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken)
  });
}

export function deleteLookbookEntry(accessToken: string, entryId: string) {
  return apiRequest<void>(`/lookbook/entries/${entryId}`, {
    method: "DELETE",
    headers: buildAuthHeaders(accessToken)
  });
}

export function createWearLogFromLookbookEntry(
  accessToken: string,
  entryId: string,
  payload: LookbookWearLogCreateRequest
) {
  return apiRequest<WearLogDetailSnapshot>(`/lookbook/entries/${entryId}/wear`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function createLookbookUploadIntent(
  accessToken: string,
  payload: LookbookUploadIntentRequest
) {
  return apiRequest<LookbookUploadIntentResponse>("/lookbook/uploads/intents", {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function completeLookbookUpload(accessToken: string, uploadIntentId: string) {
  return apiRequest<PrivateImageSnapshot>("/lookbook/uploads/complete", {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: {
      upload_intent_id: uploadIntentId
    }
  });
}
