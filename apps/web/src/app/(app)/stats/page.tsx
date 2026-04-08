import {
  BarChart3,
  Calendar,
  Clock,
  Crown,
  Flame,
  Heart,
  Moon,
  Palette,
  Repeat,
  Shirt,
  Sparkles,
  Sun,
  Tag,
  TrendingUp
} from "lucide-react";

import { listAllClosetItems } from "@/lib/closet";
import { CATEGORY_LABELS, formatMonthYear, humanizeValue } from "@/lib/companion-ui";
import {
  getInsightOverview,
  getInsightTimeline,
  listAllInsightItemUsage,
  listAllInsightOutfitUsage,
  listAllNeverWornItems
} from "@/lib/insights";
import { ApiError } from "@/lib/api";
import { requireSession } from "../../../lib/auth/session";

function getTopEntry(values: Array<string | null | undefined>) {
  const counts = new Map<string, number>();

  for (const value of values) {
    if (!value) {
      continue;
    }

    counts.set(value, (counts.get(value) ?? 0) + 1);
  }

  return [...counts.entries()].sort((left, right) => right[1] - left[1])[0] ?? null;
}

function getWeightedTopEntry(values: Array<{ value: string | null | undefined; weight: number }>) {
  const counts = new Map<string, number>();

  for (const entry of values) {
    if (!entry.value) {
      continue;
    }

    counts.set(entry.value, (counts.get(entry.value) ?? 0) + entry.weight);
  }

  return [...counts.entries()].sort((left, right) => right[1] - left[1])[0] ?? null;
}

function clampScore(value: number) {
  return Math.max(0, Math.min(10, value));
}

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
      console.error(`Failed to load stats ${label}.`, error);
      return fallback;
    }

    throw error;
  }
}

export default async function StatsPage() {
  const session = await requireSession();
  const accessToken = session.session.access_token;
  const now = new Date();
  const timelineStart = new Date(now);
  timelineStart.setDate(timelineStart.getDate() - 83);

  const [closetItems, overview, itemUsage, neverWornItems, outfitUsage, timeline] = await Promise.all([
    withApiFallback("closet items", () => listAllClosetItems(accessToken), []),
    withApiFallback("overview", () => getInsightOverview(accessToken), createEmptyOverview()),
    withApiFallback("item usage", () => listAllInsightItemUsage(accessToken), []),
    withApiFallback("never-worn items", () => listAllNeverWornItems(accessToken), []),
    withApiFallback("outfit usage", () => listAllInsightOutfitUsage(accessToken), []),
    withApiFallback(
      "timeline",
      () => getInsightTimeline(accessToken, timelineStart.toISOString().slice(0, 10), now.toISOString().slice(0, 10)),
      []
    )
  ]);

  const closetById = new Map(closetItems.map((item) => [item.item_id, item]));
  const topCategory = getTopEntry(closetItems.map((item) => item.category));
  const topColor = getTopEntry(closetItems.map((item) => item.primary_color));
  const topBrand = getTopEntry(closetItems.map((item) => item.brand));
  const mostWorn = itemUsage[0] ?? null;
  const leastWorn = neverWornItems[0] ?? itemUsage[itemUsage.length - 1] ?? null;
  const repeatedOutfits = outfitUsage.filter((item) => item.wear_count > 1).length;
  const favoriteSeason = getWeightedTopEntry(
    outfitUsage.map((item) => ({ value: item.season, weight: item.wear_count }))
  );
  const favoriteOccasion = getWeightedTopEntry(
    outfitUsage.map((item) => ({ value: item.occasion, weight: item.wear_count }))
  );
  const recentWearLogs = timeline.reduce((sum, point) => sum + point.wear_log_count, 0);
  const avgOutfitsPerWeek = recentWearLogs / 12;
  const varietyScore = clampScore(overview.current_month.active_closet_coverage_ratio * 10);

  const sections = [
    {
      title: "Overview",
      items: [
        {
          icon: <Shirt className="h-5 w-5" />,
          label: "Outfits Logged",
          value: overview.all_time.total_wear_logs.toString(),
          sub: `since ${formatMonthYear(session.user.created_at)}`,
          color: "bg-sage"
        },
        {
          icon: <Flame className="h-5 w-5 text-coral" />,
          label: "Current Streak",
          value: `${overview.streaks.current_streak_days} days`,
          sub: `your best: ${overview.streaks.longest_streak_days} days`,
          color: "bg-coral/15"
        },
        {
          icon: <TrendingUp className="h-5 w-5 text-foreground" />,
          label: "Avg. Outfits / Week",
          value: avgOutfitsPerWeek.toFixed(1),
          sub: "last 12 weeks",
          color: "bg-sage/20"
        },
        {
          icon: <Calendar className="h-5 w-5 text-sky" />,
          label: "Member Since",
          value: formatMonthYear(session.user.created_at),
          sub: `${Math.max(1, Math.round((Date.now() - new Date(session.user.created_at).getTime()) / (1000 * 60 * 60 * 24 * 30)))} months of style`,
          color: "bg-sky/20"
        }
      ]
    },
    {
      title: "Wardrobe",
      items: [
        {
          icon: <Repeat className="h-5 w-5 text-lavender" />,
          label: "Total Items",
          value: closetItems.length.toString(),
          sub: "in your closet",
          color: "bg-lavender/30"
        },
        {
          icon: <BarChart3 className="h-5 w-5 text-foreground" />,
          label: "Top Category",
          value: topCategory ? CATEGORY_LABELS[topCategory[0]] ?? humanizeValue(topCategory[0]) ?? topCategory[0] : "-",
          sub: topCategory ? `${topCategory[1]} items` : "",
          color: "bg-secondary"
        },
        {
          icon: <Palette className="h-5 w-5 text-butter" />,
          label: "Most Common Color",
          value: topColor?.[0] ? humanizeValue(topColor[0]) ?? topColor[0] : "-",
          sub: topColor ? `${topColor[1]} items` : "",
          color: "bg-butter/20"
        },
        {
          icon: <Tag className="h-5 w-5 text-coral" />,
          label: "Favorite Brand",
          value: topBrand?.[0] || "-",
          sub: topBrand ? `${topBrand[1]} items` : "",
          color: "bg-coral/10"
        }
      ]
    },
    {
      title: "Wear Habits",
      items: [
        {
          icon: <Crown className="h-5 w-5 text-butter" />,
          label: "Most Worn Item",
          value: mostWorn?.title || "-",
          sub: mostWorn
            ? `${mostWorn.wear_count} times · ${closetById.get(mostWorn.closet_item_id)?.brand ?? "Closet item"}`
            : "",
          color: "bg-butter/20"
        },
        {
          icon: <Clock className="h-5 w-5 text-muted-foreground" />,
          label: "Least Worn Item",
          value: leastWorn?.title || "-",
          sub:
            leastWorn && "wear_count" in leastWorn
              ? `${leastWorn.wear_count} times · ${closetById.get(leastWorn.closet_item_id)?.brand ?? "Closet item"}`
              : leastWorn
                ? "0 times · never worn"
                : "",
          color: "bg-secondary"
        },
        {
          icon: <Heart className="h-5 w-5 text-blush" />,
          label: "Outfit Repeats",
          value: repeatedOutfits.toString(),
          sub: "saved outfits worn more than once",
          color: "bg-blush/30"
        },
        {
          icon: <Sun className="h-5 w-5 text-butter" />,
          label: "Favorite Season",
          value: favoriteSeason?.[0] ? humanizeValue(favoriteSeason[0]) ?? favoriteSeason[0] : "-",
          sub: favoriteSeason ? `${favoriteSeason[1]} logged wears` : "not enough data yet",
          color: "bg-butter/15"
        },
        {
          icon: <Moon className="h-5 w-5 text-lavender" />,
          label: "Favorite Occasion",
          value: favoriteOccasion?.[0] ? humanizeValue(favoriteOccasion[0]) ?? favoriteOccasion[0] : "-",
          sub: favoriteOccasion ? `${favoriteOccasion[1]} logged wears` : "not enough data yet",
          color: "bg-lavender/20"
        },
        {
          icon: <Sparkles className="h-5 w-5 text-sage" />,
          label: "Style Variety Score",
          value: `${varietyScore.toFixed(1)} / 10`,
          sub: "based on current-month closet coverage",
          color: "bg-sage/20"
        }
      ]
    }
  ] as const;

  return (
    <div className="page-enter">
      <h1 className="mb-1 font-display text-4xl font-semibold tracking-editorial text-foreground">
        Your Stats
      </h1>
      <p className="mb-8 font-body text-sm text-muted-foreground">
        A deep dive into your style patterns.
      </p>

      <div className="space-y-10">
        {sections.map((section) => (
          <section key={section.title}>
            <h2 className="mb-3 font-body text-xs font-medium uppercase tracking-widest text-muted-foreground">
              {section.title}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {section.items.map((item, index) => (
                <div
                  key={item.label}
                  className="card-lift flex items-center gap-4 rounded-2xl bg-card p-4"
                  style={{
                    boxShadow: "var(--shadow-sm)",
                    animation: `revealFloat 0.72s var(--ease-soft) ${0.05 + index * 0.05}s both`
                  }}
                >
                  <div className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full ${item.color}`}>
                    {item.icon}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="mb-0.5 font-body text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      {item.label}
                    </p>
                    <p className="truncate font-body text-lg font-bold leading-tight text-foreground">
                      {item.value}
                    </p>
                    {item.sub ? (
                      <p className="mt-0.5 font-body text-xs text-muted-foreground">{item.sub}</p>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
