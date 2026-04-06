import { startTransition, useEffect, useRef, useState } from "react";
import type { ImagePickerAsset } from "expo-image-picker";

import { ApiError } from "../lib/api";
import { usePolling } from "../lib/hooks";
import {
  archiveClosetItem,
  confirmClosetReview,
  dismissSimilarityEdge,
  getClosetDuplicateItems,
  getClosetExtractionSnapshot,
  getClosetMetadataOptions,
  getClosetProcessingSnapshot,
  getClosetReviewQueue,
  getClosetReviewSnapshot,
  getClosetSimilarItems,
  getConfirmedClosetItemDetail,
  getConfirmedClosetItems,
  markSimilarityEdgeDuplicate,
  patchClosetReview,
  retryClosetReview
} from "./client";
import {
  uploadClosetAsset,
  buildLogicalRetryKey,
  createUploadIdempotencyPath,
  selectSingleImage,
  type UploadIdempotencyPath
} from "./upload";
import type {
  ClosetBrowseFilters,
  ClosetBrowseListItemSnapshot,
  ClosetDraftSnapshot,
  ClosetExtractionSnapshot,
  ClosetItemDetailSnapshot,
  ClosetItemReviewSnapshot,
  ClosetMetadataOptionsResponse,
  ClosetProcessingSnapshot,
  ClosetQueueSection,
  ClosetReviewFieldChange,
  ClosetRetryStep,
  ClosetSimilarityListItemSnapshot,
  ClosetSimilarityListResponse
} from "./types";
import { buildQueueSections } from "./status";

function appendUniqueItems<T extends { item_id?: string; id?: string }>(current: T[], next: T[]) {
  const seen = new Set(current.map((item) => item.item_id ?? item.id));
  return current.concat(next.filter((item) => !seen.has(item.item_id ?? item.id)));
}

export function useClosetMetadataOptions(accessToken?: string | null) {
  const [data, setData] = useState<ClosetMetadataOptionsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      if (!accessToken) {
        setData(null);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await getClosetMetadataOptions(accessToken);
        if (!active) {
          return;
        }

        setData(response);
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Metadata could not be loaded.");
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [accessToken]);

  return { data, error, isLoading };
}

export function useReviewQueue(accessToken?: string | null, limit = 20) {
  const [items, setItems] = useState<ClosetDraftSnapshot[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(cursor?: string | null, mode: "replace" | "append" = "replace") {
    if (!accessToken) {
      setItems([]);
      setNextCursor(null);
      setIsLoading(false);
      return;
    }

    if (mode === "replace") {
      setIsLoading(cursor == null);
      setIsRefreshing(cursor != null);
    } else {
      setIsLoadingMore(true);
    }
    setError(null);

    try {
      const response = await getClosetReviewQueue(accessToken, {
        cursor,
        limit
      });

      startTransition(() => {
        setItems((current) => (mode === "append" ? appendUniqueItems(current, response.items) : response.items));
        setNextCursor(response.next_cursor);
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Review queue could not be loaded.");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
      setIsLoadingMore(false);
    }
  }

  useEffect(() => {
    void load(undefined, "replace");
  }, [accessToken, limit]);

  return {
    error,
    isLoading,
    isLoadingMore,
    isRefreshing,
    items,
    nextCursor,
    refresh: () => load(undefined, "replace"),
    loadMore: () => {
      if (!nextCursor || isLoadingMore) {
        return Promise.resolve();
      }

      return load(nextCursor, "append");
    },
    sections: buildQueueSections(items) as ClosetQueueSection[]
  };
}

export function useConfirmedClosetBrowse(
  accessToken: string | null | undefined,
  filters: ClosetBrowseFilters,
  limit = 20
) {
  const [items, setItems] = useState<ClosetBrowseListItemSnapshot[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(cursor?: string | null, mode: "replace" | "append" = "replace") {
    if (!accessToken) {
      setItems([]);
      setNextCursor(null);
      setIsLoading(false);
      return;
    }

    if (mode === "append") {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const response = await getConfirmedClosetItems(accessToken, {
        ...filters,
        cursor,
        limit
      });

      startTransition(() => {
        setItems((current) => (mode === "append" ? appendUniqueItems(current, response.items) : response.items));
        setNextCursor(response.next_cursor);
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Closet items could not be loaded.");
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }

  useEffect(() => {
    void load(undefined, "replace");
  }, [
    accessToken,
    filters.category,
    filters.color,
    filters.material,
    filters.pattern,
    filters.query,
    filters.subcategory,
    limit
  ]);

  return {
    error,
    isLoading,
    isLoadingMore,
    items,
    nextCursor,
    refresh: () => load(undefined, "replace"),
    loadMore: () => {
      if (!nextCursor || isLoadingMore) {
        return Promise.resolve();
      }
      return load(nextCursor, "append");
    }
  };
}

export function useClosetItemDetail(accessToken?: string | null, itemId?: string | null) {
  const [detail, setDetail] = useState<ClosetItemDetailSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isArchiving, setIsArchiving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!accessToken || !itemId) {
      setDetail(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getConfirmedClosetItemDetail(accessToken, itemId);
      setDetail(response);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Closet detail could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [accessToken, itemId]);

  async function archive() {
    if (!accessToken || !itemId) {
      return false;
    }

    setIsArchiving(true);
    setError(null);

    try {
      await archiveClosetItem(accessToken, itemId);
      return true;
    } catch (archiveError) {
      setError(archiveError instanceof Error ? archiveError.message : "Archive failed.");
      return false;
    } finally {
      setIsArchiving(false);
    }
  }

  return {
    archive,
    detail,
    error,
    isArchiving,
    isLoading,
    refresh: load
  };
}

type SimilarityKind = "similar" | "duplicates";

export function useClosetSimilarity(
  accessToken?: string | null,
  itemId?: string | null,
  kind: SimilarityKind = "similar"
) {
  const [snapshot, setSnapshot] = useState<ClosetSimilarityListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!accessToken || !itemId) {
      setSnapshot(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response =
        kind === "duplicates"
          ? await getClosetDuplicateItems(accessToken, itemId)
          : await getClosetSimilarItems(accessToken, itemId);
      setSnapshot(response);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Related items could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [accessToken, itemId, kind]);

  async function applyEdgeAction(edgeId: string, action: "dismiss" | "mark_duplicate") {
    if (!accessToken) {
      return false;
    }

    setError(null);

    try {
      await (action === "dismiss"
        ? dismissSimilarityEdge(accessToken, edgeId)
        : markSimilarityEdgeDuplicate(accessToken, edgeId));

      setSnapshot((current) => {
        if (!current) {
          return current;
        }

        const nextItems = current.items.filter((item) => item.edge_id !== edgeId);
        return {
          ...current,
          items: nextItems
        };
      });
      return true;
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "The similarity action failed.");
      return false;
    }
  }

  return {
    error,
    isLoading,
    items: snapshot?.items ?? ([] as ClosetSimilarityListItemSnapshot[]),
    refresh: load,
    applyEdgeAction,
    snapshot
  };
}

function shouldPollReviewState(
  processing: ClosetProcessingSnapshot | null,
  extraction: ClosetExtractionSnapshot | null,
  review: ClosetItemReviewSnapshot | null
) {
  if (processing && ["pending", "running"].includes(processing.processing_status)) {
    return true;
  }

  if (
    extraction &&
    (["pending", "running"].includes(extraction.extraction_status) ||
      ["pending", "running"].includes(extraction.normalization_status))
  ) {
    return true;
  }

  if (!review && processing?.lifecycle_status === "processing") {
    return true;
  }

  return false;
}

export function useClosetReviewItem(accessToken?: string | null, itemId?: string | null) {
  const [processing, setProcessing] = useState<ClosetProcessingSnapshot | null>(null);
  const [extraction, setExtraction] = useState<ClosetExtractionSnapshot | null>(null);
  const [review, setReview] = useState<ClosetItemReviewSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastRefreshRef = useRef(0);

  async function load() {
    if (!accessToken || !itemId) {
      setProcessing(null);
      setExtraction(null);
      setReview(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [processingSnapshot, extractionSnapshot] = await Promise.all([
        getClosetProcessingSnapshot(accessToken, itemId),
        getClosetExtractionSnapshot(accessToken, itemId)
      ]);

      setProcessing(processingSnapshot);
      setExtraction(extractionSnapshot);

      try {
        const reviewSnapshot = await getClosetReviewSnapshot(accessToken, itemId);
        setReview(reviewSnapshot);
      } catch (reviewError) {
        if (reviewError instanceof ApiError && reviewError.code === "review_not_available") {
          setReview(null);
        } else {
          throw reviewError;
        }
      }

      lastRefreshRef.current = Date.now();
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Review detail could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [accessToken, itemId]);

  usePolling(
    () => load(),
    shouldPollReviewState(processing, extraction, review) && Date.now() - lastRefreshRef.current > 1500,
    3000
  );

  async function applyChanges(changes: ClosetReviewFieldChange[]) {
    if (!accessToken || !itemId || !review) {
      return { ok: false as const, stale: false };
    }

    setIsMutating(true);
    setError(null);

    try {
      const nextReview = await patchClosetReview(accessToken, itemId, {
        expected_review_version: review.review_version,
        changes
      });
      setReview(nextReview);
      return { ok: true as const, stale: false };
    } catch (mutationError) {
      if (mutationError instanceof ApiError && mutationError.code === "stale_review_version") {
        await load();
        return { ok: false as const, stale: true };
      }

      setError(mutationError instanceof Error ? mutationError.message : "Review update failed.");
      return { ok: false as const, stale: false };
    } finally {
      setIsMutating(false);
    }
  }

  async function confirm() {
    if (!accessToken || !itemId || !review) {
      return { ok: false as const, stale: false };
    }

    setIsMutating(true);
    setError(null);

    try {
      const nextReview = await confirmClosetReview(accessToken, itemId, {
        expected_review_version: review.review_version
      });
      setReview(nextReview);
      return { ok: true as const, stale: false };
    } catch (confirmError) {
      if (confirmError instanceof ApiError && confirmError.code === "stale_review_version") {
        await load();
        return { ok: false as const, stale: true };
      }

      setError(confirmError instanceof Error ? confirmError.message : "Confirmation failed.");
      return { ok: false as const, stale: false };
    } finally {
      setIsMutating(false);
    }
  }

  async function retry(step?: ClosetRetryStep | null) {
    if (!accessToken || !itemId) {
      return false;
    }

    setIsMutating(true);
    setError(null);

    try {
      const nextReview = await retryClosetReview(accessToken, itemId, {
        step
      });
      setReview(nextReview);
      await load();
      return true;
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Retry failed.");
      return false;
    } finally {
      setIsMutating(false);
    }
  }

  return {
    applyChanges,
    confirm,
    error,
    extraction,
    isLoading,
    isMutating,
    processing,
    refresh: load,
    retry,
    review
  };
}

export function useClosetUpload(accessToken?: string | null) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [lastAsset, setLastAsset] = useState<ImagePickerAsset | null>(null);
  const [path, setPath] = useState<UploadIdempotencyPath | null>(null);

  async function uploadAsset(asset: ImagePickerAsset) {
    if (!accessToken) {
      throw new Error("Authentication is required before uploading.");
    }

    setIsUploading(true);
    setError(null);
    setStage("Preparing image");

    const logicalKey = buildLogicalRetryKey(asset);
    const nextPath =
      path?.logical_key === logicalKey ? path : createUploadIdempotencyPath(logicalKey);

    try {
      const result = await uploadClosetAsset({
        accessToken,
        asset,
        path: nextPath,
        onStageChange: (nextStage) => setStage(nextStage)
      });
      setPath(result.path);
      setStage("Sent to review");
      return result.draft;
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed.");
      throw uploadError;
    } finally {
      setIsUploading(false);
    }
  }

  async function selectAndUpload(source: "camera" | "library") {
    const asset = await selectSingleImage(source);
    if (!asset) {
      return null;
    }

    setLastAsset(asset);
    return uploadAsset(asset);
  }

  async function retryLastUpload() {
    if (!lastAsset) {
      return null;
    }

    return uploadAsset(lastAsset);
  }

  return {
    error,
    isUploading,
    retryLastUpload,
    selectAndUpload,
    stage
  };
}
