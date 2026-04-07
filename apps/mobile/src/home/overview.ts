import { useEffect, useState } from "react";

import { apiRequest } from "../lib/api";

export type InsightOverviewResponse = {
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

export async function getInsightOverview(accessToken: string): Promise<InsightOverviewResponse> {
  return apiRequest<InsightOverviewResponse>("/insights/overview", {
    headers: {
      Authorization: `Bearer ${accessToken}`
    }
  });
}

export function useInsightOverview(accessToken?: string | null) {
  const [data, setData] = useState<InsightOverviewResponse | null>(null);
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
        const response = await getInsightOverview(accessToken);
        if (!active) {
          return;
        }

        setData(response);
      } catch (loadError) {
        if (!active) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : "Insight overview could not be loaded.");
        setData(null);
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

  return {
    data,
    error,
    isLoading
  };
}
