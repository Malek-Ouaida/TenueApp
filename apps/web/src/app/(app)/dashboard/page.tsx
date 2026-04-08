import Link from "next/link";
import { ArrowRight, BarChart3, BookOpen, Crown, Flame, Shirt, TrendingUp } from "lucide-react";

import { formatDisplayDate, getDaysAgo, getPrimaryImageUrl } from "@/lib/companion-ui";
import { getInsightOverview, listInsightItemUsagePage } from "@/lib/insights";
import { ApiError } from "@/lib/api";
import { listRecentLookbookEntries as fetchRecentLookbookEntries } from "@/lib/lookbook";
import { requireSession } from "../../../lib/auth/session";

function formatRecentLookDate(value: string) {
  const daysAgo = getDaysAgo(value);

  if (daysAgo === 0) {
    return "Today";
  }

  if (daysAgo === 1) {
    return "Yesterday";
  }

  return formatDisplayDate(value);
}

async function loadRecentLookbookEntries(accessToken: string) {
  try {
    return await fetchRecentLookbookEntries(accessToken, 12);
  } catch (error) {
    if (error instanceof ApiError) {
      console.error("Failed to load dashboard recent looks.", error);
      return [];
    }

    throw error;
  }
}

export default async function DashboardPage() {
  const session = await requireSession();
  const accessToken = session.session.access_token;
  const [overview, itemUsagePage, lookbookEntries] = await Promise.all([
    getInsightOverview(accessToken),
    listInsightItemUsagePage(accessToken, { limit: 1 }),
    loadRecentLookbookEntries(accessToken)
  ]);

  const mostWorn = itemUsagePage.items[0];
  const stats = [
    {
      icon: Shirt,
      label: "Total Items",
      value: overview.all_time.active_confirmed_closet_item_count.toString(),
      color: "bg-sage"
    },
    {
      icon: TrendingUp,
      label: "Outfits Logged",
      value: overview.all_time.total_wear_logs.toString(),
      color: "bg-lavender"
    },
    {
      icon: Flame,
      label: "Current Streak",
      value: `${overview.streaks.current_streak_days} days`,
      color: "bg-coral/20"
    },
    {
      icon: Crown,
      label: "Most Worn",
      value: mostWorn?.title?.split(" ").slice(0, 2).join(" ") || "-",
      color: "bg-butter/20"
    }
  ] as const;
  const recentLooks = lookbookEntries
    .filter((entry) => Boolean(getPrimaryImageUrl(entry.entry.image, entry.entry.outfit?.cover_image, entry.lookbook_cover_image)))
    .slice(0, 3)
    .map((entry) => ({
      id: entry.entry.id,
      imageUrl: getPrimaryImageUrl(entry.entry.image, entry.entry.outfit?.cover_image, entry.lookbook_cover_image),
      context:
        entry.entry.caption ??
        entry.entry.outfit?.title ??
        entry.entry.note_text?.slice(0, 32) ??
        entry.lookbook_title,
      dateLabel: formatRecentLookDate(entry.entry.updated_at)
    }));

  return (
    <div className="page-enter space-y-10">
      <div>
        <h1 className="mb-1 font-display text-4xl font-semibold tracking-editorial text-foreground">
          Good morning
        </h1>
        <p className="font-body text-base text-muted-foreground">
          Here&apos;s your wardrobe at a glance.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((stat, index) => (
          <div
            key={stat.label}
            className="card-lift flex items-center gap-4 rounded-2xl bg-card p-5"
            style={{
              boxShadow: "var(--shadow-sm)",
              animation: `revealFloat 0.7s var(--ease-soft) ${0.05 + index * 0.06}s both`
            }}
          >
            <div className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full ${stat.color}`}>
              <stat.icon className="h-5 w-5 text-foreground" />
            </div>
            <div className="min-w-0">
              <p className="mb-0.5 font-body text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {stat.label}
              </p>
              <p className="truncate font-body text-lg font-bold text-foreground">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          {
            label: "Browse Closet",
            path: "/closet",
            icon: Shirt,
            desc: "Search and filter your wardrobe"
          },
          { label: "View Stats", path: "/stats", icon: BarChart3, desc: "Your style insights" },
          { label: "Lookbook", path: "/lookbook", icon: BookOpen, desc: "Your saved outfits" }
        ].map((entry, index) => (
          <Link
            key={entry.path}
            href={entry.path}
            className="card-lift group flex items-center gap-4 rounded-2xl bg-card p-5"
            style={{
              boxShadow: "var(--shadow-sm)",
              animation: `revealFloat 0.78s var(--ease-soft) ${0.16 + index * 0.07}s both`
            }}
          >
            <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-secondary">
              <entry.icon className="h-5 w-5 text-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-body text-sm font-semibold text-foreground">{entry.label}</p>
              <p className="font-body text-xs text-muted-foreground">{entry.desc}</p>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground transition-colors group-hover:text-foreground" />
          </Link>
        ))}
      </div>

      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-2xl font-semibold tracking-editorial text-foreground">
            Recent Looks
          </h2>
          <Link
            href="/lookbook"
            className="flex items-center gap-1 font-body text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            See all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        {recentLooks.length === 0 ? (
          <div className="rounded-3xl bg-card px-6 py-12 text-center" style={{ boxShadow: "var(--shadow-sm)" }}>
            <p className="font-display text-2xl font-semibold text-foreground">No looks yet</p>
            <p className="mt-2 font-body text-sm text-muted-foreground">
              Save a few outfits or inspiration entries to start building your lookbook.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            {recentLooks.map((look, index) => (
              <Link
                key={look.id}
                href={`/lookbook/${look.id}`}
                className="card-lift"
                style={{ animation: `revealFloat 0.82s var(--ease-soft) ${0.24 + index * 0.07}s both` }}
              >
                <div
                  className="mb-2 aspect-[3/4] overflow-hidden rounded-2xl"
                  style={{ boxShadow: "var(--shadow-sm)" }}
                >
                  {look.imageUrl ? (
                    <img src={look.imageUrl} alt={look.context} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center px-4 text-center">
                      <span className="font-display text-lg font-semibold text-muted-foreground">
                        {look.context}
                      </span>
                    </div>
                  )}
                </div>
                <p className="font-body text-sm font-medium text-foreground">{look.context}</p>
                <p className="font-body text-xs text-muted-foreground">{look.dateLabel}</p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
