"use client";

import Link from "next/link";
import { useState } from "react";
import { Bookmark, CalendarClock, Camera, RefreshCcw, Sparkles } from "lucide-react";

export type LookbookPageEntry = {
  id: string;
  imageUrl: string | null;
  title: string;
  meta: string;
  badgeLabel: string;
  tags: string[];
  tab: "logged" | "recreate" | "inspiration" | "draft";
};

const TABS = ["All", "Logged", "Recreate", "Inspiration", "Drafts"] as const;

function emptyStateCopy(tab: (typeof TABS)[number]) {
  switch (tab) {
    case "Logged":
      return {
        title: "No saved daily looks",
        subtitle: "Save a confirmed wear log when you want to keep a real outfit in circulation."
      };
    case "Recreate":
      return {
        title: "Nothing to recreate yet",
        subtitle: "Gallery looks you want to rebuild later will show up here."
      };
    case "Inspiration":
      return {
        title: "No inspiration saved",
        subtitle: "Add a gallery photo when something is worth keeping as a future idea."
      };
    case "Drafts":
      return {
        title: "No drafts waiting",
        subtitle: "Draft looks stay hidden from the main feed until you publish them."
      };
    default:
      return {
        title: "Your lookbook is empty",
        subtitle: "Save a gallery photo or a confirmed daily log to start your feed."
      };
  }
}

export function LookbookPage({ entries }: { entries: LookbookPageEntry[] }) {
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>("All");
  const filteredEntries = entries.filter((entry) => {
    switch (activeTab) {
      case "Logged":
        return entry.tab === "logged";
      case "Recreate":
        return entry.tab === "recreate";
      case "Inspiration":
        return entry.tab === "inspiration";
      case "Drafts":
        return entry.tab === "draft";
      default:
        return entry.tab !== "draft";
    }
  });
  const empty = emptyStateCopy(activeTab);

  return (
    <div className="page-enter">
      <div className="mb-6">
        <h1 className="font-display text-4xl font-semibold tracking-editorial text-foreground">Lookbook</h1>
        <p className="mt-1 font-body text-sm text-muted-foreground">
          Private looks built from saved daily outfits and gallery photos you want to revisit.
        </p>
      </div>

      <div className="mb-8 flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`interactive-press nav-pill rounded-full px-4 py-2 font-body text-sm font-medium transition-all ${
              activeTab === tab ? "bg-foreground text-primary-foreground" : "bg-card text-muted-foreground"
            }`}
            style={{ boxShadow: activeTab === tab ? "var(--shadow-md)" : "var(--shadow-sm)" }}
          >
            {tab}
          </button>
        ))}
      </div>

      {filteredEntries.length === 0 ? (
        <div className="rounded-3xl bg-card px-6 py-12 text-center" style={{ boxShadow: "var(--shadow-sm)" }}>
          <p className="font-display text-2xl font-semibold text-foreground">{empty.title}</p>
          <p className="mt-2 font-body text-sm text-muted-foreground">{empty.subtitle}</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          {filteredEntries.map((entry, index) => (
            <Link
              key={entry.id}
              href={`/lookbook/${entry.id}`}
              className="card-lift"
              style={{ animation: `revealFloat 0.72s var(--ease-soft) ${0.05 + index * 0.05}s both` }}
            >
              <div
                className="relative mb-2 aspect-[3/4] overflow-hidden rounded-2xl bg-secondary"
                style={{ boxShadow: "var(--shadow-sm)" }}
              >
                {entry.imageUrl ? (
                  <img src={entry.imageUrl} alt={entry.title} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center px-4 text-center">
                    <span className="font-display text-lg font-semibold text-muted-foreground">{entry.title}</span>
                  </div>
                )}
                <div className="glass-frost absolute left-2 top-2 flex items-center gap-1 rounded-full bg-card/85 px-2.5 py-1.5">
                  {entry.tab === "logged" ? (
                    <CalendarClock className="h-3 w-3 text-foreground" />
                  ) : entry.tab === "recreate" ? (
                    <RefreshCcw className="h-3 w-3 text-foreground" />
                  ) : entry.tab === "draft" ? (
                    <Bookmark className="h-3 w-3 text-foreground" />
                  ) : (
                    <Sparkles className="h-3 w-3 text-foreground" />
                  )}
                  <span className="font-body text-[11px] font-semibold text-foreground">{entry.badgeLabel}</span>
                </div>
              </div>
              <p className="font-body text-sm font-medium text-foreground">{entry.title}</p>
              <p className="mt-1 font-body text-xs text-muted-foreground">{entry.meta}</p>
              {entry.tags.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {entry.tags.slice(0, 3).map((tag) => (
                    <span key={tag} className="rounded-full bg-card px-2 py-1 font-body text-[11px] text-muted-foreground">
                      {tag}
                    </span>
                  ))}
                </div>
              ) : activeTab === "All" ? null : (
                <div className="mt-2 flex items-center gap-1 font-body text-[11px] text-muted-foreground">
                  <Camera className="h-3 w-3" />
                  Saved look
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
