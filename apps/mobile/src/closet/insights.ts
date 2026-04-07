import { useEffect, useState } from "react";

import { apiRequest } from "../lib/api";
import { getConfirmedClosetItems } from "./client";
import type { ClosetBrowseListItemSnapshot } from "./types";

export type ClosetInsightMetric = {
  label: string;
  count: number;
};

export type ClosetInsightsSnapshot = {
  totalItems: number;
  processedItems: number;
  topCategory: ClosetInsightMetric | null;
  topColor: ClosetInsightMetric | null;
  topMaterial: ClosetInsightMetric | null;
  categoryMix: ClosetInsightMetric[];
  colorMix: ClosetInsightMetric[];
  materialMix: ClosetInsightMetric[];
  recentItems: ClosetBrowseListItemSnapshot[];
};

export type ClosetItemUsageSort = "most_worn" | "least_worn";

export type ClosetItemUsageSnapshot = {
  closet_item_id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  display_image: ClosetBrowseListItemSnapshot["display_image"];
  thumbnail_image: ClosetBrowseListItemSnapshot["thumbnail_image"];
  wear_count: number;
  first_worn_date: string;
  last_worn_date: string;
};

type ClosetItemUsageResponse = {
  items: ClosetItemUsageSnapshot[];
  next_cursor: string | null;
};

export type ClosetItemUsageIndexSnapshot = {
  byItemId: Record<string, ClosetItemUsageSnapshot>;
  items: ClosetItemUsageSnapshot[];
  mostWornItemId: string | null;
};

export function buildClosetInsights(
  items: ClosetBrowseListItemSnapshot[]
): ClosetInsightsSnapshot {
  const categoryMix = countValues(items.map((item) => item.category));
  const colorMix = countValues(items.map((item) => item.primary_color));
  const materialMix = countValues(items.map((item) => item.material));

  return {
    totalItems: items.length,
    processedItems: items.filter((item) => Boolean(item.display_image?.url)).length,
    topCategory: categoryMix[0] ?? null,
    topColor: colorMix[0] ?? null,
    topMaterial: materialMix[0] ?? null,
    categoryMix,
    colorMix,
    materialMix,
    recentItems: items.slice(0, 8)
  };
}

function countValues(values: Array<string | null | undefined>): ClosetInsightMetric[] {
  const counts = new Map<string, number>();

  for (const value of values) {
    if (!value) {
      continue;
    }

    counts.set(value, (counts.get(value) ?? 0) + 1);
  }

  return Array.from(counts.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => {
      if (right.count !== left.count) {
        return right.count - left.count;
      }

      return left.label.localeCompare(right.label);
    });
}

async function getClosetItemUsagePage(
  accessToken: string,
  params: {
    cursor?: string | null;
    limit?: number;
    sort?: ClosetItemUsageSort;
  } = {}
) {
  const searchParams = new URLSearchParams();

  if (params.cursor) {
    searchParams.set("cursor", params.cursor);
  }
  if (params.limit) {
    searchParams.set("limit", String(params.limit));
  }
  searchParams.set("sort", params.sort ?? "most_worn");

  return apiRequest<ClosetItemUsageResponse>(`/insights/items?${searchParams.toString()}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`
    }
  });
}

export function useClosetInsights(
  accessToken?: string | null,
  options: { maxItems?: number; pageSize?: number } = {}
) {
  const maxItems = options.maxItems ?? 60;
  const pageSize = options.pageSize ?? 20;
  const [items, setItems] = useState<ClosetBrowseListItemSnapshot[]>([]);
  const [insights, setInsights] = useState<ClosetInsightsSnapshot>(() => buildClosetInsights([]));
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      if (!accessToken) {
        setItems([]);
        setInsights(buildClosetInsights([]));
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const collected: ClosetBrowseListItemSnapshot[] = [];
        let cursor: string | null | undefined = null;

        while (active && collected.length < maxItems) {
          const response = await getConfirmedClosetItems(accessToken, {
            cursor,
            limit: Math.min(pageSize, maxItems - collected.length)
          });

          collected.push(...response.items);

          if (!response.next_cursor) {
            break;
          }

          cursor = response.next_cursor;
        }

        if (!active) {
          return;
        }

        setItems(collected);
        setInsights(buildClosetInsights(collected));
      } catch (loadError) {
        if (!active) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : "Closet insights could not be loaded.");
        setItems([]);
        setInsights(buildClosetInsights([]));
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
  }, [accessToken, maxItems, pageSize]);

  return {
    error,
    insights,
    isLoading,
    items
  };
}

export function useClosetItemUsageIndex(
  accessToken?: string | null,
  options: { maxItems?: number; pageSize?: number; sort?: ClosetItemUsageSort } = {}
) {
  const maxItems = options.maxItems ?? 80;
  const pageSize = options.pageSize ?? 20;
  const sort = options.sort ?? "most_worn";
  const [snapshot, setSnapshot] = useState<ClosetItemUsageIndexSnapshot>({
    byItemId: {},
    items: [],
    mostWornItemId: null
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      if (!accessToken) {
        setSnapshot({
          byItemId: {},
          items: [],
          mostWornItemId: null
        });
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const collected: ClosetItemUsageSnapshot[] = [];
        let cursor: string | null | undefined = null;

        while (active && collected.length < maxItems) {
          const response = await getClosetItemUsagePage(accessToken, {
            cursor,
            limit: Math.min(pageSize, maxItems - collected.length),
            sort
          });

          collected.push(...response.items);

          if (!response.next_cursor) {
            break;
          }

          cursor = response.next_cursor;
        }

        if (!active) {
          return;
        }

        const byItemId = Object.fromEntries(
          collected.map((item) => [item.closet_item_id, item])
        );

        setSnapshot({
          byItemId,
          items: collected,
          mostWornItemId: collected[0]?.closet_item_id ?? null
        });
      } catch (loadError) {
        if (!active) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : "Item usage could not be loaded.");
        setSnapshot({
          byItemId: {},
          items: [],
          mostWornItemId: null
        });
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
  }, [accessToken, maxItems, pageSize, sort]);

  return {
    error,
    isLoading,
    snapshot
  };
}
