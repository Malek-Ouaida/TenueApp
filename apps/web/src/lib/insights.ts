import { apiRequest, buildApiPath, fetchAllCursorPages, type CursorPageResponse } from "./api";
import type { ClosetProcessingImage } from "./closet";

export type InsightOverview = {
  as_of_date: string;
  all_time: {
    total_wear_logs: number;
    total_worn_item_events: number;
    unique_items_worn: number;
    active_confirmed_closet_item_count: number;
    never_worn_item_count: number;
  };
  current_month: {
    total_wear_logs: number;
    total_worn_item_events: number;
    unique_items_worn: number;
    active_closet_items_worn: number;
    active_closet_coverage_ratio: number;
  };
  streaks: {
    current_streak_days: number;
    longest_streak_days: number;
  };
};

export type InsightItemUsage = {
  closet_item_id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  display_image: ClosetProcessingImage | null;
  thumbnail_image: ClosetProcessingImage | null;
  wear_count: number;
  first_worn_date: string;
  last_worn_date: string;
};

export type InsightNeverWornItem = {
  closet_item_id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  display_image: ClosetProcessingImage | null;
  thumbnail_image: ClosetProcessingImage | null;
  confirmed_at: string;
};

export type InsightOutfitUsage = {
  id: string;
  title: string | null;
  occasion: string | null;
  season: string | null;
  source: string;
  item_count: number;
  is_favorite: boolean;
  is_archived: boolean;
  cover_image: ClosetProcessingImage | null;
  wear_count: number;
  first_worn_date: string;
  last_worn_date: string;
};

export type InsightTimelinePoint = {
  date: string;
  wear_log_count: number;
  worn_item_count: number;
  unique_item_count: number;
};

type InsightItemUsageResponse = CursorPageResponse<InsightItemUsage>;
type InsightNeverWornResponse = CursorPageResponse<InsightNeverWornItem>;
type InsightOutfitUsageResponse = CursorPageResponse<InsightOutfitUsage>;
type InsightTimelineResponse = {
  start_date: string;
  end_date: string;
  points: InsightTimelinePoint[];
};

function authHeaders(accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`
  };
}

export async function getInsightOverview(accessToken: string) {
  return apiRequest<InsightOverview>("/insights/overview", {
    headers: authHeaders(accessToken),
    ttlSeconds: 10
  });
}

export async function listInsightItemUsagePage(
  accessToken: string,
  options: {
    sort?: "most_worn" | "least_worn";
    limit?: number;
    cursor?: string | null;
  } = {}
) {
  const { sort = "most_worn", limit = 50, cursor = null } = options;
  return apiRequest<InsightItemUsageResponse>(buildApiPath("/insights/items", { cursor, limit, sort }), {
    headers: authHeaders(accessToken),
    ttlSeconds: 10
  });
}

export async function listAllInsightItemUsage(accessToken: string, sort: "most_worn" | "least_worn" = "most_worn") {
  return fetchAllCursorPages((cursor) => listInsightItemUsagePage(accessToken, { cursor, limit: 50, sort }));
}

export async function listAllNeverWornItems(accessToken: string) {
  return fetchAllCursorPages((cursor) =>
    apiRequest<InsightNeverWornResponse>(buildApiPath("/insights/never-worn", { cursor, limit: 50 }), {
      headers: authHeaders(accessToken),
      ttlSeconds: 10
    })
  );
}

export async function listAllInsightOutfitUsage(accessToken: string) {
  return fetchAllCursorPages((cursor) =>
    apiRequest<InsightOutfitUsageResponse>(buildApiPath("/insights/outfits", { cursor, limit: 50 }), {
      headers: authHeaders(accessToken),
      ttlSeconds: 10
    })
  );
}

export async function getInsightTimeline(accessToken: string, startDate: string, endDate: string) {
  const response = await apiRequest<InsightTimelineResponse>(
    buildApiPath("/insights/timeline", { start_date: startDate, end_date: endDate }),
    {
      headers: authHeaders(accessToken),
      ttlSeconds: 10
    }
  );

  return response.points;
}
