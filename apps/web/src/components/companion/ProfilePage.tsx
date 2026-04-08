"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import {
  BarChart3,
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Crown,
  Flame,
  List,
  Settings,
  Shirt,
  X
} from "lucide-react";

import type { Profile } from "@/lib/profile";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS_FULL = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December"
];
const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

type ProfilePageProps = {
  email: string;
  profile: Profile | null;
  wearEntries: ProfileWearEntry[];
  stats: ProfileStatsSummary;
};

export type ProfileWearEntry = {
  id: string;
  date: string;
  imageUrl: string | null;
  route: string;
  title: string;
};

export type ProfileStatsSummary = {
  totalOutfits: number;
  currentStreak: number;
  mostWornTitle: string;
};

export function ProfilePage({ email, profile, wearEntries, stats }: ProfilePageProps) {
  const router = useRouter();
  const [now] = useState(() => new Date());
  const [viewMonth, setViewMonth] = useState(now.getMonth());
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [slideDir, setSlideDir] = useState<"left" | "right" | null>(null);
  const [showStats, setShowStats] = useState(false);
  const [viewMode, setViewMode] = useState<"calendar" | "timeline">("calendar");
  const startX = useRef(0);
  const dragging = useRef(false);

  const displayName = profile?.display_name?.trim() || deriveDisplayName(email);
  const avatarLabel = getInitial(displayName, email);
  const styleName = displayName.split(/\s+/)[0] || displayName;
  const outfitData = wearEntries.reduce<Record<string, ProfileWearEntry>>((accumulator, entry) => {
    accumulator[entry.date] = entry;
    return accumulator;
  }, {});
  const totalOutfits = stats.totalOutfits;
  const currentStreak = stats.currentStreak;
  const mostWornTitle = stats.mostWornTitle;
  const isCurrentMonth = viewMonth === now.getMonth() && viewYear === now.getFullYear();

  const changeMonth = (delta: number) => {
    setSlideDir(delta > 0 ? "left" : "right");
    setTimeout(() => {
      const nextDate = new Date(viewYear, viewMonth + delta, 1);
      setViewMonth(nextDate.getMonth());
      setViewYear(nextDate.getFullYear());
      setSlideDir(null);
    }, 180);
  };

  const onPointerDown = (event: React.PointerEvent) => {
    dragging.current = true;
    startX.current = event.clientX;
  };

  const onPointerUp = (event: React.PointerEvent) => {
    if (!dragging.current) {
      return;
    }

    dragging.current = false;
    const delta = event.clientX - startX.current;

    if (delta < -50) {
      changeMonth(1);
    } else if (delta > 50) {
      changeMonth(-1);
    }
  };

  const firstDay = new Date(viewYear, viewMonth, 1);
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const startDayOfWeek = firstDay.getDay();
  const cells: Array<number | null> = [];

  for (let index = 0; index < startDayOfWeek; index += 1) {
    cells.push(null);
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push(day);
  }

  while (cells.length % 7 !== 0) {
    cells.push(null);
  }

  const todayString = now.toISOString().split("T")[0];
  const timelineEntries = wearEntries
    .filter((entry) => {
      const [year, month] = entry.date.split("-").map(Number);
      return year === viewYear && month - 1 === viewMonth;
    })
    .sort((left, right) => right.date.localeCompare(left.date));

  return (
    <div className="page-enter w-full">
      <div className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div
            className="flex h-14 w-14 items-center justify-center rounded-full"
            style={{
              background: "linear-gradient(135deg, hsl(var(--lavender)), hsl(var(--blush)))",
              boxShadow: "0 3px 12px hsl(var(--lavender) / 0.4)"
            }}
          >
            <span className="font-display text-xl font-semibold text-foreground">{avatarLabel}</span>
          </div>
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-editorial text-foreground">
              {styleName}
            </h1>
            <p className="font-body text-sm text-muted-foreground">Your style story</p>
          </div>
        </div>

        <Link
          href="/settings"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary transition-colors hover:bg-secondary/80"
          style={{ boxShadow: "var(--shadow-sm)" }}
        >
          <Settings className="h-4 w-4 text-muted-foreground" />
        </Link>
      </div>

      <button type="button" onClick={() => setShowStats(true)} className="mb-8 grid w-full grid-cols-3 gap-3 text-left">
        {[
          {
            icon: <Shirt className="h-4 w-4" />,
            label: "Logged",
            value: totalOutfits.toString(),
            color: "bg-sage"
          },
          {
            icon: <Flame className="h-4 w-4 text-coral" />,
            label: "Streak",
            value: `${currentStreak}d`,
            color: "bg-coral/15"
          },
          {
            icon: <Crown className="h-4 w-4 text-butter" />,
            label: "Most worn",
            value: mostWornTitle.split(" ").slice(0, 2).join(" ") || "-",
            color: "bg-butter/20"
          }
        ].map((stat) => (
          <div
            key={stat.label}
            className="flex items-center gap-3 rounded-2xl bg-card p-4 transition-colors hover:bg-secondary/50"
            style={{ boxShadow: "var(--shadow-sm)" }}
          >
            <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full ${stat.color}`}>
              {stat.icon}
            </div>
            <div className="min-w-0">
              <p className="mb-0.5 font-body text-[10px] font-medium uppercase leading-none tracking-wider text-muted-foreground">
                {stat.label}
              </p>
              <p className="truncate font-body text-base font-bold leading-none text-foreground">
                {stat.value}
              </p>
            </div>
          </div>
        ))}
      </button>

      <Link
        href="/stats"
        className="card-lift mb-8 flex items-center justify-between rounded-2xl bg-card px-5 py-4"
        style={{ boxShadow: "var(--shadow-sm)" }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sage/20">
            <BarChart3 className="h-5 w-5 text-foreground" />
          </div>
          <div>
            <p className="font-body text-sm font-semibold text-foreground">See All Stats</p>
            <p className="font-body text-xs text-muted-foreground">Full wardrobe insights</p>
          </div>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
      </Link>

      <div className="rounded-3xl bg-card p-6" style={{ boxShadow: "var(--shadow-sm)" }}>
        <div className="mb-5 flex items-center justify-between">
          <button
            type="button"
            onClick={() => changeMonth(-1)}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary transition-colors hover:bg-secondary/80"
          >
            <ChevronLeft className="h-4 w-4 text-foreground" />
          </button>

          <div className="flex items-center gap-3">
            <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
              {MONTHS_FULL[viewMonth]} {viewYear}
            </h2>
            <div className="flex rounded-full bg-secondary p-0.5">
              <button
                type="button"
                onClick={() => setViewMode("calendar")}
                className={`flex h-8 w-8 items-center justify-center rounded-full transition-all duration-200 ${
                  viewMode === "calendar" ? "bg-card shadow-sm" : ""
                }`}
              >
                <CalendarIcon
                  className="h-4 w-4"
                  style={{
                    color:
                      viewMode === "calendar"
                        ? "hsl(var(--foreground))"
                        : "hsl(var(--muted-foreground))"
                  }}
                />
              </button>
              <button
                type="button"
                onClick={() => setViewMode("timeline")}
                className={`flex h-8 w-8 items-center justify-center rounded-full transition-all duration-200 ${
                  viewMode === "timeline" ? "bg-card shadow-sm" : ""
                }`}
              >
                <List
                  className="h-4 w-4"
                  style={{
                    color:
                      viewMode === "timeline"
                        ? "hsl(var(--foreground))"
                        : "hsl(var(--muted-foreground))"
                  }}
                />
              </button>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              if (!isCurrentMonth) {
                changeMonth(1);
              }
            }}
            className={`flex h-9 w-9 items-center justify-center rounded-full bg-secondary transition-colors hover:bg-secondary/80 ${
              isCurrentMonth ? "pointer-events-none opacity-25" : ""
            }`}
          >
            <ChevronRight className="h-4 w-4 text-foreground" />
          </button>
        </div>

        {viewMode === "calendar" ? (
          <>
            <div className="mb-2 grid grid-cols-7 gap-1">
              {DAYS.map((day) => (
                <div key={day} className="text-center font-display text-xs font-medium italic text-muted-foreground">
                  {day}
                </div>
              ))}
            </div>

            <div
              className="grid grid-cols-7 gap-1"
              onPointerDown={onPointerDown}
              onPointerUp={onPointerUp}
              style={{
                animation: slideDir
                  ? `${slideDir === "left" ? "slideInRight" : "slideInLeft"} 0.2s ease-out`
                  : undefined
              }}
            >
              {cells.map((day, index) => {
                if (day === null) {
                  return <div key={`empty-${index}`} className="aspect-[3/4]" />;
                }

                const dateString = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const wearEntry = outfitData[dateString];
                const outfitImage = wearEntry?.imageUrl ?? null;
                const isToday = dateString === todayString;
                const isFuture = new Date(dateString) > now;

                return (
                  <button
                    key={dateString}
                    type="button"
                    onClick={() => {
                      if (wearEntry) {
                        router.push(wearEntry.route);
                      }
                    }}
                    disabled={isFuture}
                    className={`relative aspect-[3/4] overflow-hidden rounded-lg transition-transform hover:scale-105 ${
                      isFuture ? "opacity-25" : ""
                    } ${!outfitImage && !isFuture ? "cursor-default" : "cursor-pointer"}`}
                    style={{
                      backgroundColor:
                        outfitImage ? undefined : wearEntry ? "hsl(var(--sage) / 0.16)" : "hsl(var(--secondary))",
                      boxShadow: isToday
                        ? "inset 0 0 0 2px hsl(var(--coral))"
                        : wearEntry
                          ? "0 1px 3px rgba(0,0,0,0.06)"
                          : "none"
                    }}
                  >
                    {outfitImage ? (
                      <img
                        src={outfitImage}
                        alt=""
                        className="absolute inset-0 h-full w-full object-cover"
                        draggable={false}
                      />
                    ) : wearEntry ? (
                      <div className="absolute inset-0 flex items-end justify-start p-1.5">
                        <span className="rounded-full bg-card/90 px-2 py-0.5 font-body text-[9px] font-semibold uppercase tracking-[0.18em] text-foreground">
                          Worn
                        </span>
                      </div>
                    ) : null}
                    <span
                      className={`absolute left-[5px] top-[3px] z-10 font-body text-[10px] font-semibold ${
                        outfitImage
                          ? "text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)]"
                          : wearEntry
                            ? "text-foreground"
                            : "text-muted-foreground"
                      }`}
                    >
                      {day}
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        ) : (
          <div className="space-y-3">
            {timelineEntries.length === 0 ? (
              <div className="flex flex-col items-center py-16">
                <Shirt className="mb-3 h-8 w-8 text-muted-foreground" />
                <p className="font-body text-sm font-medium text-muted-foreground">
                  No outfits this month
                </p>
              </div>
            ) : (
              timelineEntries.map((entry) => {
                const date = new Date(`${entry.date}T00:00:00`);
                const dayNumber = date.getDate();
                const dayName = DAYS[date.getDay()];

                return (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => router.push(entry.route)}
                    className="flex w-full items-center gap-4 rounded-2xl bg-secondary/30 p-3 text-left transition-colors hover:bg-secondary/60"
                  >
                    <div className="flex w-12 flex-shrink-0 flex-col items-center">
                      <span className="font-body text-[11px] font-medium uppercase text-muted-foreground">
                        {dayName}
                      </span>
                      <span className="font-display text-xl font-semibold text-foreground">
                        {dayNumber}
                      </span>
                    </div>
                    <div className="h-12 w-px self-center rounded-full bg-border" />
                    <div
                      className="h-20 w-16 flex-shrink-0 overflow-hidden rounded-xl"
                      style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
                    >
                      {entry.imageUrl ? (
                        <img src={entry.imageUrl} alt="" className="h-full w-full object-cover" draggable={false} />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-secondary px-3 text-center">
                          <span className="font-display text-xs font-semibold text-muted-foreground">
                            {entry.title}
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-body text-sm font-semibold text-foreground">
                        {MONTHS_SHORT[date.getMonth()]} {dayNumber}
                      </p>
                      <p className="mt-0.5 font-body text-xs text-muted-foreground">Outfit logged</p>
                    </div>
                    <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground/50" />
                  </button>
                );
              })
            )}
          </div>
        )}
      </div>

      <div
        className={`fixed inset-0 z-50 transition-opacity duration-300 ${
          showStats ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <button
          type="button"
          aria-label="Close stats"
          onClick={() => setShowStats(false)}
          className="absolute inset-0 bg-black/25"
        />
        <div
          className={`absolute inset-x-0 bottom-0 mx-auto w-full max-w-xl rounded-t-[2rem] bg-card transition-transform duration-500 ${
            showStats ? "translate-y-0" : "translate-y-full"
          }`}
          style={{ boxShadow: "0 -12px 48px rgba(0,0,0,0.14)" }}
        >
          <div className="mx-auto mt-3 h-1.5 w-12 rounded-full bg-border" />
          <div className="flex items-start justify-between px-6 pb-2 pt-4 text-left">
            <div>
              <h2 className="font-display text-xl font-semibold text-foreground">Your Stats</h2>
              <p className="font-body text-sm text-muted-foreground">Quick overview</p>
            </div>
            <button
              type="button"
              onClick={() => setShowStats(false)}
              className="interactive-press flex h-9 w-9 items-center justify-center rounded-full bg-secondary"
            >
              <X className="h-4 w-4 text-foreground" />
            </button>
          </div>
          <div className="space-y-3 px-6 pb-4">
            {[
              {
                icon: <Shirt className="h-5 w-5" />,
                label: "Outfits Logged",
                value: totalOutfits.toString(),
                color: "bg-sage"
              },
              {
                icon: <Flame className="h-5 w-5 text-coral" />,
                label: "Current Streak",
                value: `${currentStreak} days`,
                color: "bg-coral/15"
              },
              {
                icon: <Crown className="h-5 w-5 text-butter" />,
                label: "Most Worn",
                value: mostWornTitle,
                color: "bg-butter/20"
              }
            ].map((stat) => (
              <div key={stat.label} className="flex items-center gap-4 rounded-2xl bg-secondary/50 p-4">
                <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full ${stat.color}`}>
                  {stat.icon}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="mb-0.5 font-body text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    {stat.label}
                  </p>
                  <p className="truncate font-body text-lg font-bold leading-none text-foreground">
                    {stat.value}
                  </p>
                </div>
              </div>
            ))}
          </div>
          <div className="px-6 pb-8">
            <button
              type="button"
              onClick={() => {
                setShowStats(false);
                router.push("/stats");
              }}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-foreground font-body text-sm font-semibold text-background transition-opacity hover:opacity-90"
              style={{ boxShadow: "var(--shadow-md)" }}
            >
              See All Stats
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function deriveDisplayName(email: string) {
  const localPart = email.split("@")[0] || "Tenue";
  return localPart
    .split(/[._-]+/)
    .filter(Boolean)
    .map((segment) => segment[0]?.toUpperCase() + segment.slice(1))
    .join(" ");
}

function getInitial(displayName: string, email: string) {
  const source = displayName || email;
  return source.trim().charAt(0).toUpperCase() || "T";
}
