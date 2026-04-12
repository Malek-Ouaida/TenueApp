import { startTransition, useEffect, useState } from "react";

import type { WearLogDetailSnapshot } from "../wear/types";
import {
  archiveLookbookEntry,
  createLookbookEntry,
  createWearLogFromLookbookEntry,
  deleteLookbookEntry,
  getLookbookEntries,
  getLookbookEntry,
  updateLookbookEntry
} from "./client";
import type {
  LookbookEntryCreateRequest,
  LookbookEntryDetailSnapshot,
  LookbookEntryFilters,
  LookbookEntrySummarySnapshot,
  LookbookEntryUpdateRequest,
  LookbookWearLogCreateRequest
} from "./types";

function appendUniqueItems<T extends { id: string }>(current: T[], next: T[]) {
  const seen = new Set(current.map((item) => item.id));
  return current.concat(next.filter((item) => !seen.has(item.id)));
}

export function useLookbookEntries(
  accessToken?: string | null,
  filters: LookbookEntryFilters = {},
  limit = 24
) {
  const [items, setItems] = useState<LookbookEntrySummarySnapshot[]>([]);
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
      const response = await getLookbookEntries(accessToken, {
        ...filters,
        cursor,
        limit
      });

      startTransition(() => {
        setItems((current) => (mode === "append" ? appendUniqueItems(current, response.items) : response.items));
        setNextCursor(response.next_cursor);
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Lookbook entries could not be loaded.");
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }

  useEffect(() => {
    void load(undefined, "replace");
  }, [
    accessToken,
    filters.has_linked_items,
    filters.include_archived,
    filters.intent,
    filters.occasion_tag,
    filters.season_tag,
    filters.source_kind,
    filters.status,
    filters.style_tag,
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

export function useLookbookEntryDetail(accessToken?: string | null, entryId?: string | null) {
  const [detail, setDetail] = useState<LookbookEntryDetailSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!accessToken || !entryId) {
      setDetail(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getLookbookEntry(accessToken, entryId);
      setDetail(response);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Lookbook detail could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [accessToken, entryId]);

  async function mutate<T>(
    callback: () => Promise<T>,
    onSuccess: (result: T) => void
  ) {
    if (!accessToken || !entryId) {
      return null;
    }

    setIsMutating(true);
    setError(null);

    try {
      const response = await callback();
      onSuccess(response);
      return response;
    } catch (mutationError) {
      setError(mutationError instanceof Error ? mutationError.message : "Lookbook update failed.");
      return null;
    } finally {
      setIsMutating(false);
    }
  }

  return {
    detail,
    error,
    isLoading,
    isMutating,
    refresh: load,
    setDetail,
    update: (payload: LookbookEntryUpdateRequest) =>
      mutate(
        () => updateLookbookEntry(accessToken!, entryId!, payload),
        (response) => {
          setDetail(response);
        }
      ),
    archive: () =>
      mutate(
        () => archiveLookbookEntry(accessToken!, entryId!),
        () => {
          setDetail((current) => (current ? { ...current, archived_at: new Date().toISOString() } : current));
        }
      ),
    remove: () =>
      mutate(
        () => deleteLookbookEntry(accessToken!, entryId!),
        () => {
          setDetail(null);
        }
      ),
    startWearLog: (payload: LookbookWearLogCreateRequest) =>
      mutate(
        () => createWearLogFromLookbookEntry(accessToken!, entryId!, payload),
        () => {}
      ) as Promise<WearLogDetailSnapshot | null>
  };
}

export async function createLookbookEntryWithSession(
  accessToken: string,
  payload: LookbookEntryCreateRequest
) {
  return createLookbookEntry(accessToken, payload);
}

export async function updateLookbookEntryWithSession(
  accessToken: string,
  entryId: string,
  payload: LookbookEntryUpdateRequest
) {
  return updateLookbookEntry(accessToken, entryId, payload);
}
