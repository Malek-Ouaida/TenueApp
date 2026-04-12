"use client";

import Link from "next/link";
import { ArrowLeft, Calendar, Clock3, Tag } from "lucide-react";

export type LookbookDetailItem = {
  id: string;
  title: string;
  imageUrl: string | null;
  meta: string | null;
};

type LookbookEntryDetailProps = {
  backHref: string;
  imageUrl: string | null;
  title: string;
  subtitle: string;
  badgeLabel: string;
  statusLabel: string;
  dateLabel: string;
  notes: string | null;
  caption: string | null;
  tags: string[];
  itemCount: number;
  sourceMeta: string | null;
  items: LookbookDetailItem[];
  canWearThisLook: boolean;
};

export function LookbookEntryDetail({
  backHref,
  imageUrl,
  title,
  subtitle,
  badgeLabel,
  statusLabel,
  dateLabel,
  notes,
  caption,
  tags,
  itemCount,
  sourceMeta,
  items,
  canWearThisLook
}: LookbookEntryDetailProps) {
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
          <div className="glass-frost absolute left-4 top-4 rounded-full bg-card/85 px-3 py-1.5">
            <span className="font-body text-xs font-semibold text-foreground">{badgeLabel}</span>
          </div>
        </div>

        <div className="space-y-6">
          <div>
            <div className="mb-3 flex flex-wrap gap-2">
              <span className="rounded-full bg-foreground px-3 py-1.5 font-body text-xs font-semibold text-primary-foreground">
                {statusLabel}
              </span>
              {tags.slice(0, 3).map((tag) => (
                <span key={tag} className="rounded-full bg-card px-3 py-1.5 font-body text-xs text-muted-foreground">
                  {tag}
                </span>
              ))}
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-editorial text-foreground">{title}</h1>
            <p className="mt-2 font-body text-base text-muted-foreground">{subtitle}</p>
            <div className="mt-3 flex flex-wrap items-center gap-4">
              <span className="flex items-center gap-1.5 font-body text-sm text-muted-foreground">
                <Calendar className="h-3.5 w-3.5" />
                {dateLabel}
              </span>
              <span className="flex items-center gap-1.5 font-body text-sm text-muted-foreground">
                <Tag className="h-3.5 w-3.5" />
                {itemCount} items
              </span>
            </div>
            {sourceMeta ? (
              <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-card px-3 py-1.5 font-body text-xs text-muted-foreground">
                <Clock3 className="h-3.5 w-3.5" />
                {sourceMeta}
              </div>
            ) : null}
          </div>

          {caption ? (
            <p className="font-body text-base leading-relaxed text-foreground">{caption}</p>
          ) : null}

          {notes ? (
            <div className="rounded-3xl bg-card p-5" style={{ boxShadow: "var(--shadow-sm)" }}>
              <h3 className="mb-2 font-body text-xs uppercase tracking-wider text-muted-foreground">Notes</h3>
              <p className="font-body text-base italic leading-relaxed text-muted-foreground">&quot;{notes}&quot;</p>
            </div>
          ) : null}

          <div>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-body text-xs uppercase tracking-wider text-muted-foreground">Linked Closet Items</h3>
              {!canWearThisLook ? (
                <span className="font-body text-xs text-muted-foreground">Link items in mobile to power wear logging.</span>
              ) : null}
            </div>
            {items.length > 0 ? (
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
                    {item.meta ? <p className="truncate font-body text-[11px] text-muted-foreground">{item.meta}</p> : null}
                  </Link>
                ))}
              </div>
            ) : (
              <div className="rounded-3xl bg-card px-5 py-6" style={{ boxShadow: "var(--shadow-sm)" }}>
                <p className="font-body text-sm text-muted-foreground">
                  This look does not have linked closet items yet.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
