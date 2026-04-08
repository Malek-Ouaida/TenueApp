"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, Calendar, Heart, Tag } from "lucide-react";

export type LookbookDetailItem = {
  id: string;
  title: string;
  imageUrl: string | null;
};

type LookbookEntryDetailProps = {
  backHref: string;
  imageUrl: string | null;
  title: string;
  dateLabel: string;
  itemCount: number;
  notes: string;
  items: LookbookDetailItem[];
};

export function LookbookEntryDetail({
  backHref,
  imageUrl,
  title,
  dateLabel,
  itemCount,
  notes,
  items
}: LookbookEntryDetailProps) {
  const [liked, setLiked] = useState(false);

  return (
    <div className="page-enter">
      <Link
        href={backHref}
        className="mb-6 inline-flex items-center gap-2 font-body text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back to lookbook
      </Link>

      <div className="grid gap-8 md:grid-cols-2">
        <div
          className="relative aspect-[3/4] overflow-hidden rounded-3xl bg-secondary"
          style={{ boxShadow: "var(--shadow-lg)" }}
        >
          {imageUrl ? (
            <img src={imageUrl} alt={title} className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center px-8 text-center">
              <span className="font-display text-3xl font-semibold text-muted-foreground">{title}</span>
            </div>
          )}
          <button
            type="button"
            onClick={() => setLiked((current) => !current)}
            className="glass-frost absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-card/80"
          >
            <Heart className={`h-5 w-5 transition-colors ${liked ? "fill-coral text-coral" : "text-foreground"}`} />
          </button>
        </div>

        <div className="space-y-6">
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-editorial text-foreground">{title}</h1>
            <div className="mt-2 flex items-center gap-4">
              <span className="flex items-center gap-1.5 font-body text-sm text-muted-foreground">
                <Calendar className="h-3.5 w-3.5" />
                {dateLabel}
              </span>
              <span className="flex items-center gap-1.5 font-body text-sm text-muted-foreground">
                <Tag className="h-3.5 w-3.5" />
                {itemCount} items
              </span>
            </div>
          </div>

          <p className="font-body text-base italic leading-relaxed text-muted-foreground">&quot;{notes}&quot;</p>

          {items.length > 0 ? (
            <div>
              <h3 className="mb-3 font-body text-xs uppercase tracking-wider text-muted-foreground">Items worn</h3>
              <div className="grid grid-cols-3 gap-3">
                {items.map((item) => (
                  <Link key={item.id} href={`/closet/${item.id}`} className="card-lift">
                    <div
                      className="mb-1.5 aspect-square overflow-hidden rounded-2xl bg-secondary"
                      style={{ boxShadow: "var(--shadow-sm)" }}
                    >
                      {item.imageUrl ? (
                        <img src={item.imageUrl} alt={item.title} className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center px-3 text-center">
                          <span className="font-display text-sm font-semibold text-muted-foreground">{item.title}</span>
                        </div>
                      )}
                    </div>
                    <p className="truncate font-body text-xs text-foreground">{item.title}</p>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
