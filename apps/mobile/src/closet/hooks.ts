import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import type { ImagePickerAsset } from "expo-image-picker";

import { ApiError } from "../lib/api";
import { usePolling } from "../lib/hooks";
import {
  archiveClosetItem,
  confirmClosetReview,
  dismissSimilarityEdge,
  getClosetDuplicateItems,
  getClosetExtractionSnapshot,
  getClosetItemHistory,
  getClosetMetadataOptions,
  getClosetProcessingSnapshot,
  getClosetReviewQueue,
  getClosetReviewSnapshot,
  getClosetSimilarItems,
  getConfirmedClosetItemDetail,
  getConfirmedClosetItems,
  markSimilarityEdgeDuplicate,
  restoreClosetItem,
  patchClosetReview,
  retryClosetReview
} from "./client";
import {
  getClosetBatchUploadSnapshot,
  subscribeToClosetBatchUpload,
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
  ClosetHistoryEventSnapshot,
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

type ClosetReviewItemSnapshots = {
  cachedAt: number;
  extraction: ClosetExtractionSnapshot | null;
  processing: ClosetProcessingSnapshot | null;
  review: ClosetItemReviewSnapshot | null;
};

const REVIEW_ITEM_CACHE_TTL_MS = 60_000;
const REVIEW_QUEUE_CACHE_TTL_MS = 30_000;
const reviewItemSnapshotCache = new Map<string, ClosetReviewItemSnapshots>();
const reviewItemSnapshotInflight = new Map<string, Promise<ClosetReviewItemSnapshots>>();
const reviewQueueCache = new Map<
  string,
  {
    cachedAt: number;
    items: ClosetDraftSnapshot[];
    nextCursor: string | null;
  }
>();

function buildReviewItemCacheKey(accessToken: string, itemId: string) {
  return `${accessToken}:${itemId}`;
}

function buildReviewQueueCacheKey(accessToken: string, limit: number) {
  return `${accessToken}:queue:${limit}`;
}

function getCachedReviewItemSnapshots(cacheKey: string) {
  const cached = reviewItemSnapshotCache.get(cacheKey) ?? null;
  if (!cached) {
    return null;
  }

  if (Date.now() - cached.cachedAt > REVIEW_ITEM_CACHE_TTL_MS) {
    reviewItemSnapshotCache.delete(cacheKey);
    return null;
  }

  return cached;
}

function storeReviewItemSnapshots(
  cacheKey: string,
  snapshots: Omit<ClosetReviewItemSnapshots, "cachedAt">
) {
  const nextSnapshots = {
    ...snapshots,
    cachedAt: Date.now()
  } satisfies ClosetReviewItemSnapshots;
  reviewItemSnapshotCache.set(cacheKey, nextSnapshots);
  return nextSnapshots;
}

async function fetchReviewItemSnapshots(accessToken: string, itemId: string) {
  const cacheKey = buildReviewItemCacheKey(accessToken, itemId);
  const inFlight = reviewItemSnapshotInflight.get(cacheKey);
  if (inFlight) {
    return inFlight;
  }

  const request = (async () => {
    const [processingResult, extractionResult, reviewResult] = await Promise.allSettled([
      getClosetProcessingSnapshot(accessToken, itemId),
      getClosetExtractionSnapshot(accessToken, itemId),
      getClosetReviewSnapshot(accessToken, itemId)
    ]);

    const processing =
      processingResult.status === "fulfilled" ? processingResult.value : null;
    const extraction =
      extractionResult.status === "fulfilled" ? extractionResult.value : null;

    let review: ClosetItemReviewSnapshot | null = null;
    if (reviewResult.status === "fulfilled") {
      review = reviewResult.value;
    } else if (!(reviewResult.reason instanceof ApiError && reviewResult.reason.code === "review_not_available")) {
      throw reviewResult.reason;
    }

    if (!processing && !extraction && !review) {
      throw (
        (processingResult.status === "rejected" && processingResult.reason) ||
        (extractionResult.status === "rejected" && extractionResult.reason) ||
        new Error("Review snapshots could not be loaded.")
      );
    }

    return storeReviewItemSnapshots(cacheKey, {
      extraction,
      processing,
      review
    });
  })().finally(() => {
    reviewItemSnapshotInflight.delete(cacheKey);
  });

  reviewItemSnapshotInflight.set(cacheKey, request);
  return request;
}

export function prefetchClosetReviewItem(accessToken?: string | null, itemId?: string | null) {
  if (!accessToken || !itemId) {
    return Promise.resolve();
  }

  const cacheKey = buildReviewItemCacheKey(accessToken, itemId);
  if (getCachedReviewItemSnapshots(cacheKey)) {
    return Promise.resolve();
  }

  return fetchReviewItemSnapshots(accessToken, itemId)
    .then(() => undefined)
    .catch(() => undefined);
}

function getCachedReviewQueue(cacheKey: string) {
  const cached = reviewQueueCache.get(cacheKey) ?? null;
  if (!cached) {
    return null;
  }

  if (Date.now() - cached.cachedAt > REVIEW_QUEUE_CACHE_TTL_MS) {
    reviewQueueCache.delete(cacheKey);
    return null;
  }

  return cached;
}

function storeReviewQueue(
  cacheKey: string,
  payload: {
    items: ClosetDraftSnapshot[];
    nextCursor: string | null;
  }
) {
  const cached = {
    ...payload,
    cachedAt: Date.now()
  };
  reviewQueueCache.set(cacheKey, cached);
  return cached;
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

export function useReviewQueue(
  accessToken?: string | null,
  limit = 20,
  options: { disableCache?: boolean } = {}
) {
  const disableCache = options.disableCache ?? false;
  const [items, setItems] = useState<ClosetDraftSnapshot[]>(() => {
    if (disableCache || !accessToken) {
      return [];
    }

    return getCachedReviewQueue(buildReviewQueueCacheKey(accessToken, limit))?.items ?? [];
  });
  const [nextCursor, setNextCursor] = useState<string | null>(() => {
    if (disableCache || !accessToken) {
      return null;
    }

    return getCachedReviewQueue(buildReviewQueueCacheKey(accessToken, limit))?.nextCursor ?? null;
  });
  const [isLoading, setIsLoading] = useState(() => disableCache || !accessToken || items.length === 0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(
    cursor?: string | null,
    mode: "replace" | "append" = "replace",
    options: { silent?: boolean } = {}
  ) {
    if (!accessToken) {
      setItems([]);
      setNextCursor(null);
      setIsLoading(false);
      return;
    }

    if (mode === "replace") {
      if (options.silent) {
        setIsRefreshing(true);
      } else {
        setIsLoading(cursor == null);
        setIsRefreshing(cursor != null);
      }
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
        setItems((current) => {
          const nextItems = mode === "append" ? appendUniqueItems(current, response.items) : response.items;
          const cacheKey = !disableCache ? buildReviewQueueCacheKey(accessToken, limit) : null;
          if (cacheKey) {
            storeReviewQueue(cacheKey, {
              items: nextItems,
              nextCursor: response.next_cursor
            });
          }
          return nextItems;
        });
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
    if (!accessToken) {
      setItems([]);
      setNextCursor(null);
      setIsLoading(false);
      return;
    }

    const cachedQueue = !disableCache
      ? getCachedReviewQueue(buildReviewQueueCacheKey(accessToken, limit))
      : null;

    if (cachedQueue) {
      setItems(cachedQueue.items);
      setNextCursor(cachedQueue.nextCursor);
      setIsLoading(false);
      void load(undefined, "replace", { silent: true });
      return;
    }

    setItems([]);
    setNextCursor(null);
    setIsLoading(true);
    void load(undefined, "replace");
  }, [accessToken, disableCache, limit]);

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
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(cursor?: string | null, mode: "replace" | "append" = "replace") {
    if (!accessToken) {
      setItems([]);
      setNextCursor(null);
      setIsLoading(false);
      setIsRefreshing(false);
      return;
    }

    if (mode === "append") {
      setIsLoadingMore(true);
    } else if (items.length > 0) {
      setIsRefreshing(true);
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
      setIsRefreshing(false);
      setIsLoadingMore(false);
    }
  }

  useEffect(() => {
    void load(undefined, "replace");
  }, [
    accessToken,
    filters.category,
    filters.color,
    filters.include_archived,
    filters.material,
    filters.pattern,
    filters.query,
    filters.subcategory,
    limit
  ]);

  return {
    error,
    isLoading,
    isRefreshing,
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

export function useClosetItemDetail(
  accessToken?: string | null,
  itemId?: string | null,
  options: { includeArchived?: boolean } = {}
) {
  const includeArchived = options.includeArchived ?? false;
  const [detail, setDetail] = useState<ClosetItemDetailSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isArchiving, setIsArchiving] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken || !itemId) {
      setDetail(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getConfirmedClosetItemDetail(accessToken, itemId, {
        includeArchived
      });
      setDetail(response);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Closet detail could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, includeArchived, itemId]);

  useEffect(() => {
    void load();
  }, [load]);

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

  async function restore() {
    if (!accessToken || !itemId) {
      return false;
    }

    setIsRestoring(true);
    setError(null);

    try {
      await restoreClosetItem(accessToken, itemId);
      return true;
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Restore failed.");
      return false;
    } finally {
      setIsRestoring(false);
    }
  }

  return {
    archive,
    detail,
    error,
    isArchiving,
    isLoading,
    isRestoring,
    refresh: load,
    restore,
    setDetail
  };
}

export function useClosetItemHistory(accessToken?: string | null, itemId?: string | null, limit = 50) {
  const [items, setItems] = useState<ClosetHistoryEventSnapshot[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(cursor?: string | null, mode: "replace" | "append" = "replace") {
    if (!accessToken || !itemId) {
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
      const response = await getClosetItemHistory(accessToken, itemId, {
        cursor,
        limit
      });

      startTransition(() => {
        setItems((current) =>
          mode === "append" ? appendUniqueItems(current, response.items) : response.items
        );
        setNextCursor(response.next_cursor);
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Closet history could not be loaded.");
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }

  useEffect(() => {
    void load(undefined, "replace");
  }, [accessToken, itemId, limit]);

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
  const reviewRef = useRef<ClosetItemReviewSnapshot | null>(null);
  const cacheKey =
    accessToken && itemId ? buildReviewItemCacheKey(accessToken, itemId) : null;

  async function load(options: { silent?: boolean } = {}) {
    if (!accessToken || !itemId) {
      setProcessing(null);
      setExtraction(null);
      setReview(null);
      reviewRef.current = null;
      setIsLoading(false);
      return;
    }

    if (!options.silent) {
      setIsLoading(true);
    }
    setError(null);

    try {
      const snapshots = await fetchReviewItemSnapshots(accessToken, itemId);

      reviewRef.current = snapshots.review;
      startTransition(() => {
        setProcessing(snapshots.processing);
        setExtraction(snapshots.extraction);
        setReview(snapshots.review);
      });

      lastRefreshRef.current = Date.now();
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Review detail could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!accessToken || !itemId) {
      return;
    }

    const nextCacheKey = buildReviewItemCacheKey(accessToken, itemId);
    const cached = getCachedReviewItemSnapshots(nextCacheKey);

    if (cached) {
      reviewRef.current = cached.review;
      startTransition(() => {
        setProcessing(cached.processing);
        setExtraction(cached.extraction);
        setReview(cached.review);
      });
      setIsLoading(false);
      void load({ silent: true });
      return;
    }

    setProcessing(null);
    setExtraction(null);
    setReview(null);
    reviewRef.current = null;
    void load();
  }, [accessToken, itemId]);

  usePolling(
    () => load(),
    shouldPollReviewState(processing, extraction, review) && Date.now() - lastRefreshRef.current > 1500,
    3000
  );

  async function applyChanges(changes: ClosetReviewFieldChange[]) {
    const currentReview = reviewRef.current;

    if (!accessToken || !itemId || !currentReview) {
      return { ok: false as const, stale: false };
    }

    setIsMutating(true);
    setError(null);

    try {
      const nextReview = await patchClosetReview(accessToken, itemId, {
        expected_review_version: currentReview.review_version,
        changes
      });
      reviewRef.current = nextReview;
      setReview(nextReview);
      if (cacheKey) {
        storeReviewItemSnapshots(cacheKey, {
          extraction,
          processing,
          review: nextReview
        });
      }
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
    const currentReview = reviewRef.current;

    if (!accessToken || !itemId || !currentReview) {
      return { ok: false as const, stale: false };
    }

    setIsMutating(true);
    setError(null);

    try {
      const nextReview = await confirmClosetReview(accessToken, itemId, {
        expected_review_version: currentReview.review_version
      });
      reviewRef.current = nextReview;
      setReview(nextReview);
      if (cacheKey) {
        storeReviewItemSnapshots(cacheKey, {
          extraction,
          processing,
          review: nextReview
        });
      }
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
      if (cacheKey) {
        storeReviewItemSnapshots(cacheKey, {
          extraction,
          processing,
          review: nextReview
        });
      }
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
      setStage("Sent to processing");
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

export function useClosetBatchUpload() {
  const [snapshot, setSnapshot] = useState(() => getClosetBatchUploadSnapshot());

  useEffect(() => subscribeToClosetBatchUpload(setSnapshot), []);

  return snapshot;
}
