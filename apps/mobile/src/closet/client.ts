import { apiRequest } from "../lib/api";
import type {
  ClosetBrowseFilters,
  ClosetBrowseListResponse,
  ClosetConfirmRequest,
  ClosetDraftSnapshot,
  ClosetExtractionSnapshot,
  ClosetHistoryResponse,
  ClosetItemDetailSnapshot,
  ClosetItemReviewSnapshot,
  ClosetMetadataOptionsResponse,
  ClosetProcessingSnapshot,
  ClosetRetryRequest,
  ClosetReviewListResponse,
  ClosetReviewPatchRequest,
  ClosetSimilarityEdgeSnapshot,
  ClosetSimilarityListResponse,
  ClosetUploadIntentRequest,
  ClosetUploadIntentResponse
} from "./types";

function buildAuthHeaders(accessToken: string, extraHeaders?: Record<string, string>) {
  return {
    Authorization: `Bearer ${accessToken}`,
    ...extraHeaders
  };
}

function buildQueryString(params: Record<string, string | number | null | undefined>) {
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

export function getClosetMetadataOptions(accessToken: string) {
  return apiRequest<ClosetMetadataOptionsResponse>("/closet/metadata/options", {
    headers: buildAuthHeaders(accessToken)
  });
}

export function createClosetDraft(
  accessToken: string,
  title: string | null,
  idempotencyKey: string
) {
  return apiRequest<ClosetDraftSnapshot>("/closet/drafts", {
    method: "POST",
    headers: buildAuthHeaders(accessToken, {
      "Idempotency-Key": idempotencyKey
    }),
    body: {
      title
    }
  });
}

export function getClosetDraft(accessToken: string, itemId: string) {
  return apiRequest<ClosetDraftSnapshot>(`/closet/drafts/${itemId}`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function createClosetUploadIntent(
  accessToken: string,
  itemId: string,
  payload: ClosetUploadIntentRequest
) {
  return apiRequest<ClosetUploadIntentResponse>(`/closet/drafts/${itemId}/upload-intents`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function completeClosetUpload(
  accessToken: string,
  itemId: string,
  uploadIntentId: string,
  idempotencyKey: string
) {
  return apiRequest<ClosetDraftSnapshot>(`/closet/drafts/${itemId}/uploads/complete`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken, {
      "Idempotency-Key": idempotencyKey
    }),
    body: {
      upload_intent_id: uploadIntentId
    }
  });
}

export function getClosetReviewQueue(
  accessToken: string,
  params: { cursor?: string | null; limit?: number } = {}
) {
  return apiRequest<ClosetReviewListResponse>(
    `/closet/review${buildQueryString(params)}`,
    {
      headers: buildAuthHeaders(accessToken)
    }
  );
}

export function getClosetProcessingSnapshot(accessToken: string, itemId: string) {
  return apiRequest<ClosetProcessingSnapshot>(`/closet/items/${itemId}/processing`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function getClosetExtractionSnapshot(accessToken: string, itemId: string) {
  return apiRequest<ClosetExtractionSnapshot>(`/closet/items/${itemId}/extraction`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function getClosetReviewSnapshot(accessToken: string, itemId: string) {
  return apiRequest<ClosetItemReviewSnapshot>(`/closet/items/${itemId}/review`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function patchClosetReview(
  accessToken: string,
  itemId: string,
  payload: ClosetReviewPatchRequest
) {
  return apiRequest<ClosetItemReviewSnapshot>(`/closet/items/${itemId}`, {
    method: "PATCH",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function confirmClosetReview(
  accessToken: string,
  itemId: string,
  payload: ClosetConfirmRequest
) {
  return apiRequest<ClosetItemReviewSnapshot>(`/closet/items/${itemId}/confirm`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function retryClosetReview(
  accessToken: string,
  itemId: string,
  payload: ClosetRetryRequest = {}
) {
  return apiRequest<ClosetItemReviewSnapshot>(`/closet/items/${itemId}/retry`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: payload
  });
}

export function reprocessClosetItem(accessToken: string, itemId: string, idempotencyKey: string) {
  return apiRequest<ClosetProcessingSnapshot>(`/closet/items/${itemId}/reprocess`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken, {
      "Idempotency-Key": idempotencyKey
    })
  });
}

export function reextractClosetItem(accessToken: string, itemId: string, idempotencyKey: string) {
  return apiRequest<ClosetExtractionSnapshot>(`/closet/items/${itemId}/reextract`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken, {
      "Idempotency-Key": idempotencyKey
    })
  });
}

export function getConfirmedClosetItems(
  accessToken: string,
  params: ClosetBrowseFilters & { cursor?: string | null; limit?: number }
) {
  return apiRequest<ClosetBrowseListResponse>(
    `/closet/items${buildQueryString(params)}`,
    {
      headers: buildAuthHeaders(accessToken)
    }
  );
}

export function getConfirmedClosetItemDetail(accessToken: string, itemId: string) {
  return apiRequest<ClosetItemDetailSnapshot>(`/closet/items/${itemId}`, {
    headers: buildAuthHeaders(accessToken)
  });
}

export function getClosetItemHistory(
  accessToken: string,
  itemId: string,
  params: { cursor?: string | null; limit?: number } = {}
) {
  return apiRequest<ClosetHistoryResponse>(
    `/closet/items/${itemId}/history${buildQueryString(params)}`,
    {
      headers: buildAuthHeaders(accessToken)
    }
  );
}

export function archiveClosetItem(accessToken: string, itemId: string) {
  return apiRequest<void>(`/closet/items/${itemId}/archive`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken)
  });
}

export function getClosetSimilarItems(accessToken: string, itemId: string, limit = 20) {
  return apiRequest<ClosetSimilarityListResponse>(
    `/closet/items/${itemId}/similar${buildQueryString({ limit })}`,
    {
      headers: buildAuthHeaders(accessToken)
    }
  );
}

export function getClosetDuplicateItems(accessToken: string, itemId: string, limit = 20) {
  return apiRequest<ClosetSimilarityListResponse>(
    `/closet/items/${itemId}/duplicates${buildQueryString({ limit })}`,
    {
      headers: buildAuthHeaders(accessToken)
    }
  );
}

export function dismissSimilarityEdge(accessToken: string, edgeId: string) {
  return apiRequest<ClosetSimilarityEdgeSnapshot>(`/closet/similarity/${edgeId}/dismiss`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken)
  });
}

export function markSimilarityEdgeDuplicate(accessToken: string, edgeId: string) {
  return apiRequest<ClosetSimilarityEdgeSnapshot>(
    `/closet/similarity/${edgeId}/mark-duplicate`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken)
    }
  );
}
