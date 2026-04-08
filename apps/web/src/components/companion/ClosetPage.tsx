"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Search, SlidersHorizontal, X } from "lucide-react";

import { CATEGORY_LABELS } from "@/lib/companion-ui";

export type ClosetPageItem = {
  id: string;
  title: string;
  category: string;
  categoryLabel: string;
  imageUrl: string | null;
  tag: string | null;
  color: string | null;
  seasonTags: string[];
  addedDaysAgo: number;
  timesWorn: number;
  lastWornDaysAgo: number | null;
};

const DEFAULT_CATEGORIES = [
  { id: "all", label: "All" },
  { id: "tops", label: "Tops" },
  { id: "bottoms", label: "Bottoms" },
  { id: "dresses", label: "Dresses" },
  { id: "outerwear", label: "Outerwear" },
  { id: "shoes", label: "Shoes" },
  { id: "bags", label: "Bags" },
  { id: "accessories", label: "Accessories" }
] as const;

const SORT_OPTIONS = ["Newest first", "Oldest first", "Most worn", "Least worn", "Recently worn"] as const;

export function ClosetPage({ items }: { items: ClosetPageItem[] }) {
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showFilter, setShowFilter] = useState(false);
  const [sortBy, setSortBy] = useState<(typeof SORT_OPTIONS)[number]>("Newest first");
  const [colorFilter, setColorFilter] = useState("All");
  const [seasonFilter, setSeasonFilter] = useState("All");

  const colorFilters = ["All", ...new Set(items.map((item) => item.color).filter((value): value is string => Boolean(value)))];
  const seasonFilters = [
    "All",
    ...new Set(items.flatMap((item) => item.seasonTags).filter((value) => value.length > 0))
  ];

  const categories = [
    ...DEFAULT_CATEGORIES,
    ...items
      .map((item) => item.category)
      .filter((value) => !DEFAULT_CATEGORIES.some((entry) => entry.id === value))
      .filter((value, index, values) => values.indexOf(value) === index)
      .map((value) => ({
        id: value,
        label: CATEGORY_LABELS[value] ?? value
      }))
  ];

  const filtered = items
    .filter((item) => {
      const matchesCategory = selectedCategory === "all" || item.category === selectedCategory;
      const matchesSearch = item.title.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesColor = colorFilter === "All" || item.color === colorFilter;
      const matchesSeason = seasonFilter === "All" || item.seasonTags.includes(seasonFilter);

      return matchesCategory && matchesSearch && matchesColor && matchesSeason;
    })
    .sort((left, right) => {
      switch (sortBy) {
        case "Oldest first":
          return right.addedDaysAgo - left.addedDaysAgo;
        case "Most worn":
          return right.timesWorn - left.timesWorn;
        case "Least worn":
          return left.timesWorn - right.timesWorn;
        case "Recently worn":
          return (left.lastWornDaysAgo ?? 9999) - (right.lastWornDaysAgo ?? 9999);
        default:
          return left.addedDaysAgo - right.addedDaysAgo;
      }
    });

  const hasActiveFilters = colorFilter !== "All" || seasonFilter !== "All" || sortBy !== "Newest first";

  return (
    <div className="page-enter">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-4xl font-semibold tracking-editorial text-foreground">Closet</h1>
          <p className="mt-1 font-body text-sm text-muted-foreground">Your confirmed wardrobe</p>
        </div>
        <button
          type="button"
          onClick={() => setShowFilter((current) => !current)}
          className="interactive-press relative flex h-11 w-11 items-center justify-center rounded-full bg-card"
          style={{ boxShadow: "var(--shadow-sm)" }}
        >
          <SlidersHorizontal className="h-5 w-5 text-foreground" />
          {hasActiveFilters ? <div className="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full bg-coral" /> : null}
        </button>
      </div>

      <div className="mb-5">
        <div
          className="flex items-center gap-3 rounded-full bg-card px-5 py-3"
          style={{ boxShadow: "var(--shadow-sm)" }}
        >
          <Search className="h-5 w-5 flex-shrink-0 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search your closet"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="flex-1 bg-transparent font-body text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
        </div>
      </div>

      <div className="scrollbar-hide mb-6 flex gap-2.5 overflow-x-auto pb-1">
        {categories.map((category) => (
          <button
            key={category.id}
            type="button"
            onClick={() => setSelectedCategory(category.id)}
            className={`interactive-press flex-shrink-0 whitespace-nowrap rounded-full px-5 py-2.5 font-body text-sm transition-all ${
              selectedCategory === category.id
                ? "bg-butter font-bold text-foreground"
                : "bg-card font-medium text-foreground"
            }`}
            style={{
              boxShadow:
                selectedCategory === category.id ? "0 2px 10px hsl(var(--butter) / 0.2)" : "var(--shadow-sm)"
            }}
          >
            {category.label}
          </button>
        ))}
      </div>

      {showFilter ? (
        <div className="panel-pop mb-6 rounded-3xl bg-card p-6" style={{ boxShadow: "var(--shadow-md)" }}>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg font-semibold text-foreground">Filter &amp; Sort</h3>
            <button
              type="button"
              onClick={() => setShowFilter(false)}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-secondary"
            >
              <X className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>

          <div className="space-y-5">
            <div>
              <p className="mb-2 font-body text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Sort by
              </p>
              <div className="flex flex-wrap gap-2">
                {SORT_OPTIONS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setSortBy(option)}
                    className={`interactive-press rounded-full px-4 py-2 font-body text-xs font-medium transition-all ${
                      sortBy === option ? "bg-foreground text-primary-foreground" : "bg-secondary text-foreground"
                    }`}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 font-body text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Color
              </p>
              <div className="flex flex-wrap gap-2">
                {colorFilters.map((color) => (
                  <button
                    key={color}
                    type="button"
                    onClick={() => setColorFilter(color)}
                    className={`interactive-press rounded-full px-3.5 py-2 font-body text-xs font-medium transition-all ${
                      colorFilter === color ? "bg-coral text-primary-foreground" : "bg-secondary text-foreground"
                    }`}
                  >
                    {color}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 font-body text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Season
              </p>
              <div className="flex flex-wrap gap-2">
                {seasonFilters.map((season) => (
                  <button
                    key={season}
                    type="button"
                    onClick={() => setSeasonFilter(season)}
                    className={`interactive-press rounded-full px-3.5 py-2 font-body text-xs font-medium transition-all ${
                      seasonFilter === season ? "bg-coral text-primary-foreground" : "bg-secondary text-foreground"
                    }`}
                  >
                    {season}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setSortBy("Newest first");
                  setColorFilter("All");
                  setSeasonFilter("All");
                }}
                className="h-11 flex-1 rounded-2xl bg-secondary font-body text-sm font-semibold text-foreground"
              >
                Reset
              </button>
              <button
                type="button"
                onClick={() => setShowFilter(false)}
                className="flex h-11 flex-1 items-center justify-center gap-2 rounded-2xl bg-foreground font-body text-sm font-semibold text-primary-foreground"
              >
                <Check className="h-4 w-4" />
                Apply
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="mb-6 flex gap-2">
        <span
          className="rounded-full bg-card px-3.5 py-1.5 font-body text-xs font-medium text-muted-foreground"
          style={{ boxShadow: "var(--shadow-sm)" }}
        >
          {filtered.length} items
        </span>
        <span
          className="rounded-full bg-card px-3.5 py-1.5 font-body text-xs font-medium text-muted-foreground"
          style={{ boxShadow: "var(--shadow-sm)" }}
        >
          {sortBy}
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-3xl bg-card px-6 py-12 text-center" style={{ boxShadow: "var(--shadow-sm)" }}>
          <p className="font-display text-2xl font-semibold text-foreground">No items yet</p>
          <p className="mt-2 font-body text-sm text-muted-foreground">
            Confirm a few closet items and they will show up here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {filtered.map((item, index) => (
            <Link
              key={item.id}
              href={`/closet/${item.id}`}
              className="card-lift rounded-3xl bg-card p-3"
              style={{
                boxShadow: "var(--shadow-sm)",
                animation: `fadeUp 0.35s cubic-bezier(0.32, 0.72, 0, 1) ${Math.min(index * 0.04, 0.3)}s both`
              }}
            >
              <div className="mb-3 aspect-[3/4] w-full overflow-hidden rounded-2xl bg-secondary">
                {item.imageUrl ? (
                  <img src={item.imageUrl} alt={item.title} className="h-full w-full object-cover" loading="lazy" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center px-4 text-center">
                    <span className="font-display text-lg font-semibold text-muted-foreground">{item.categoryLabel}</span>
                  </div>
                )}
              </div>
              <p className="mb-1.5 line-clamp-2 font-body text-sm font-semibold leading-tight text-foreground">
                {item.title}
              </p>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-body text-xs text-muted-foreground">{item.categoryLabel}</span>
                {item.tag ? (
                  <>
                    <span className="h-[3px] w-[3px] rounded-full bg-muted-foreground" />
                    <span className="rounded-xl bg-lavender px-2 py-0.5 font-body text-[10px] font-semibold text-foreground">
                      {item.tag}
                    </span>
                  </>
                ) : null}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
