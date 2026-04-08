"use client";

import Link from "next/link";
import { useState } from "react";
import { Sparkles, StickyNote } from "lucide-react";

export type LookbookPageEntry = {
  id: string;
  imageUrl: string | null;
  type: "outfit" | "inspiration";
  dateLabel: string;
  context: string;
  items: number;
  isNote: boolean;
};

const TABS = ["All", "Favorites", "Inspiration"] as const;

export function LookbookPage({ entries }: { entries: LookbookPageEntry[] }) {
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>("All");

  const filteredEntries = entries.filter((entry) => {
    if (activeTab === "All") {
      return true;
    }

    if (activeTab === "Favorites") {
      return entry.type === "outfit";
    }

    return entry.type === "inspiration";
  });

  return (
    <div className="page-enter">
      <div className="mb-6">
        <h1 className="font-display text-4xl font-semibold tracking-editorial text-foreground">Lookbook</h1>
        <p className="mt-1 font-body text-sm text-muted-foreground">
          The ones you&apos;ll want to wear again
        </p>
      </div>

      <div className="mb-8 flex gap-2">
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
          <p className="font-display text-2xl font-semibold text-foreground">No lookbook entries yet</p>
          <p className="mt-2 font-body text-sm text-muted-foreground">
            Logged outfits and saved inspiration will show up here.
          </p>
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
                  <img src={entry.imageUrl} alt={entry.context} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center px-4 text-center">
                    <span className="font-display text-lg font-semibold text-muted-foreground">{entry.context}</span>
                  </div>
                )}
                {entry.type === "inspiration" ? (
                  <div className="glass-frost absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-card/80">
                    {entry.isNote ? (
                      <StickyNote className="h-3 w-3 text-foreground" />
                    ) : (
                      <Sparkles className="h-3 w-3 text-foreground" />
                    )}
                  </div>
                ) : null}
              </div>
              <p className="font-body text-sm font-medium text-foreground">{entry.context}</p>
              <p className="font-body text-xs text-muted-foreground">
                {entry.dateLabel}
                {entry.items > 0 ? ` · ${entry.items} items` : ""}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
