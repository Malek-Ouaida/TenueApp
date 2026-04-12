import { startTransition, useEffect, useState } from "react";

import { usePolling } from "../lib/hooks";
import {
  confirmWearLog,
  createWearLog,
  createWearUploadIntent,
  deleteWearLog,
  getWearCalendar,
  getWearLogDetail,
  getWearLogs,
  reprocessWearLog,
  updateWearLog
} from "./client";
import { formatLocalDate, shiftDate } from "./dates";
import type {
  WearCalendarDaySnapshot,
  WearLogConfirmRequest,
  WearLogCreateRequest,
  WearLogDetailSnapshot,
  WearLogTimelineItemSnapshot,
  WearLogUpdateRequest,
  WearUploadIntentRequest
} from "./types";

function appendUniqueItems<T extends { id: string }>(current: T[], next: T[]) {
  const seen = new Set(current.map((item) => item.id));
  return current.concat(next.filter((item) => !seen.has(item.id)));
}

async function loadWearCalendarRange(
  accessToken: string,
  params: { startDate: string; endDate: string }
) {
  return getWearCalendar(accessToken, {
    start_date: params.startDate,
    end_date: params.endDate
  });
}

function shouldPollWearLog(detail: WearLogDetailSnapshot | null) {
  return detail?.status === "processing";
}

export function useWearTimeline(
  accessToken?: string | null,
  filters: {
    wear_date?: string | null;
    status?: string | null;
    include_archived?: boolean;
  } = {},
  limit = 20
) {
  const [items, setItems] = useState<WearLogTimelineItemSnapshot[]>([]);
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
      const response = await getWearLogs(accessToken, {
        ...filters,
        cursor,
        limit
      });

      startTransition(() => {
        setItems((current) => (mode === "append" ? appendUniqueItems(current, response.items) : response.items));
        setNextCursor(response.next_cursor);
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Wear history could not be loaded.");
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }

  useEffect(() => {
    void load(undefined, "replace");
  }, [accessToken, filters.include_archived, filters.status, filters.wear_date, limit]);

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

export function useWearCalendar(accessToken?: string | null, totalDays = 14) {
  const [days, setDays] = useState<WearCalendarDaySnapshot[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!accessToken) {
      setDays([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const endDate = new Date();
      endDate.setHours(12, 0, 0, 0);
      const startDate = shiftDate(endDate, -(totalDays - 1));
      const response = await loadWearCalendarRange(accessToken, {
        startDate: formatLocalDate(startDate),
        endDate: formatLocalDate(endDate)
      });
      setDays(response.days);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Wear calendar could not be loaded.");
      setDays([]);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [accessToken, totalDays]);

  return {
    days,
    error,
    isLoading,
    refresh: load
  };
}

export function useWearCalendarRange(
  accessToken?: string | null,
  params: { startDate?: string | null; endDate?: string | null } = {}
) {
  const startDate = params.startDate ?? null;
  const endDate = params.endDate ?? null;
  const [days, setDays] = useState<WearCalendarDaySnapshot[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!accessToken || !startDate || !endDate) {
      setDays([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await loadWearCalendarRange(accessToken, {
        startDate,
        endDate
      });
      setDays(response.days);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Wear calendar could not be loaded.");
      setDays([]);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [accessToken, endDate, startDate]);

  return {
    days,
    error,
    isLoading,
    refresh: load
  };
}

export function useWearLogDetail(accessToken?: string | null, wearLogId?: string | null) {
  const [detail, setDetail] = useState<WearLogDetailSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(options: { silent?: boolean } = {}) {
    if (!accessToken || !wearLogId) {
      setDetail(null);
      setIsLoading(false);
      return;
    }

    if (!options.silent) {
      setIsLoading(true);
    }
    setError(null);

    try {
      const response = await getWearLogDetail(accessToken, wearLogId);
      setDetail(response);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Wear log detail could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [accessToken, wearLogId]);

  usePolling(
    () => load({ silent: true }),
    shouldPollWearLog(detail),
    3000
  );

  async function mutate<T>(
    callback: () => Promise<T>,
    onSuccess: (response: T) => void
  ) {
    if (!accessToken || !wearLogId) {
      return null;
    }

    setIsMutating(true);
    setError(null);

    try {
      const response = await callback();
      onSuccess(response);
      return response;
    } catch (mutationError) {
      setError(mutationError instanceof Error ? mutationError.message : "Wear log update failed.");
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
    refresh: () => load(),
    setDetail,
    update: (payload: WearLogUpdateRequest) =>
      mutate(
        () => updateWearLog(accessToken!, wearLogId!, payload),
        (response) => {
          setDetail(response);
        }
      ),
    confirm: (payload: WearLogConfirmRequest) =>
      mutate(
        () => confirmWearLog(accessToken!, wearLogId!, payload),
        (response) => {
          setDetail(response);
        }
      ),
    reprocess: () =>
      mutate(
        () => reprocessWearLog(accessToken!, wearLogId!),
        (response) => {
          setDetail(response);
        }
      ),
    remove: () =>
      mutate(
        () => deleteWearLog(accessToken!, wearLogId!),
        () => {
          setDetail(null);
        }
      )
  };
}

export async function createWearLogWithSession(accessToken: string, payload: WearLogCreateRequest) {
  return createWearLog(accessToken, payload);
}

export async function createWearUploadIntentWithSession(
  accessToken: string,
  wearLogId: string,
  payload: WearUploadIntentRequest
) {
  return createWearUploadIntent(accessToken, wearLogId, payload);
}
