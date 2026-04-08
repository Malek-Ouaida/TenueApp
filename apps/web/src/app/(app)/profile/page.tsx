import { ProfilePage } from "@/components/companion/ProfilePage";
import { ApiError } from "@/lib/api";
import { getPrimaryImageUrl, humanizeValue } from "@/lib/companion-ui";
import { getInsightOverview, listInsightItemUsagePage } from "@/lib/insights";
import { listAllWearLogs } from "@/lib/wear";
import { requireSession } from "../../../lib/auth/session";
import { getCurrentProfile } from "../../../lib/profile";

function createEmptyOverview() {
  return {
    as_of_date: new Date().toISOString().slice(0, 10),
    all_time: {
      total_wear_logs: 0,
      total_worn_item_events: 0,
      unique_items_worn: 0,
      active_confirmed_closet_item_count: 0,
      never_worn_item_count: 0
    },
    current_month: {
      total_wear_logs: 0,
      total_worn_item_events: 0,
      unique_items_worn: 0,
      active_closet_items_worn: 0,
      active_closet_coverage_ratio: 0
    },
    streaks: {
      current_streak_days: 0,
      longest_streak_days: 0
    }
  };
}

async function withApiFallback<T>(label: string, load: () => Promise<T>, fallback: T) {
  try {
    return await load();
  } catch (error) {
    if (error instanceof ApiError) {
      console.error(`Failed to load profile ${label}.`, error);
      return fallback;
    }

    throw error;
  }
}

export default async function ProfileRoutePage() {
  const session = await requireSession();
  const accessToken = session.session.access_token;
  let profile = null;

  try {
    profile = await getCurrentProfile(accessToken);
  } catch {
    profile = null;
  }

  const [overview, itemUsagePage, wearLogs] = await Promise.all([
    withApiFallback("overview", () => getInsightOverview(accessToken), createEmptyOverview()),
    withApiFallback("item usage", () => listInsightItemUsagePage(accessToken, { limit: 1 }), {
      items: [],
      next_cursor: null
    }),
    withApiFallback("wear history", () => listAllWearLogs(accessToken), [])
  ]);

  return (
    <ProfilePage
      email={session.user.email}
      profile={profile}
      wearEntries={wearLogs.map((entry) => ({
        id: entry.id,
        date: entry.wear_date,
        imageUrl: getPrimaryImageUrl(entry.cover_image),
        route: "/lookbook",
        title: entry.outfit_title ?? humanizeValue(entry.context) ?? "Outfit logged"
      }))}
      stats={{
        totalOutfits: overview.all_time.total_wear_logs,
        currentStreak: overview.streaks.current_streak_days,
        mostWornTitle: itemUsagePage.items[0]?.title ?? "No wear data yet"
      }}
    />
  );
}
