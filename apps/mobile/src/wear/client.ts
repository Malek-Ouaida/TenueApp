import { apiRequest } from "../lib/api";
import type {
  WearCalendarResponse,
  WearLogConfirmRequest,
  WearLogCreateRequest,
  WearLogDetailSnapshot,
  WearLogTimelineResponse,
  WearLogUpdateRequest,
  WearUploadIntentRequest,
  WearUploadIntentResponse
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

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

export function createWearLog(accessToken: string, payload: WearLogCreateRequest) {
  return apiRequest<WearLogDetailSnapshot>("/wear-logs", {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function getWearLogs(
  accessToken: string,
  params: {
    cursor?: string | null;
    limit?: number;
    wear_date?: string | null;
    status?: string | null;
    include_archived?: boolean;
  } = {}
) {
  return apiRequest<WearLogTimelineResponse>(`/wear-logs${buildQueryString(params)}`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function getWearCalendar(
  accessToken: string,
  params: { start_date: string; end_date: string }
) {
  return apiRequest<WearCalendarResponse>(`/wear-logs/calendar${buildQueryString(params)}`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function getWearLogDetail(accessToken: string, wearLogId: string) {
  return apiRequest<WearLogDetailSnapshot>(`/wear-logs/${wearLogId}`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function updateWearLog(
  accessToken: string,
  wearLogId: string,
  payload: WearLogUpdateRequest
) {
  return apiRequest<WearLogDetailSnapshot>(`/wear-logs/${wearLogId}`, {
    method: "PATCH",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function createWearUploadIntent(
  accessToken: string,
  wearLogId: string,
  payload: WearUploadIntentRequest
) {
  return apiRequest<WearUploadIntentResponse>(`/wear-logs/${wearLogId}/photos/upload-intents`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function completeWearUpload(
  accessToken: string,
  wearLogId: string,
  uploadIntentId: string
) {
  return apiRequest<WearLogDetailSnapshot>(`/wear-logs/${wearLogId}/photos/uploads/complete`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: {
      upload_intent_id: uploadIntentId
    }
  });
}

export function confirmWearLog(
  accessToken: string,
  wearLogId: string,
  payload: WearLogConfirmRequest
) {
  return apiRequest<WearLogDetailSnapshot>(`/wear-logs/${wearLogId}/confirm`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function reprocessWearLog(accessToken: string, wearLogId: string) {
  return apiRequest<WearLogDetailSnapshot>(`/wear-logs/${wearLogId}/reprocess`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken)
  });
}

export function deleteWearLog(accessToken: string, wearLogId: string) {
  return apiRequest<void>(`/wear-logs/${wearLogId}`, {
    method: "DELETE",
    headers: buildAuthHeaders(accessToken)
  });
}
