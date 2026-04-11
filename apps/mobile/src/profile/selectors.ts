import type { ImageSourcePropType } from "react-native";

import type { ClosetInsightsSnapshot } from "../closet/insights";
import {
  dateKey,
  formatDayName,
  formatFullDate,
  type LookbookEntry,
  type OutfitEntry
} from "../lib/reference/wardrobe";
import type { Profile } from "./types";

export type ProfileRecentLook = {
  dateKey: string;
  image: ImageSourcePropType | { uri: string } | null;
  itemCount: number;
  note: string | null;
  subtitle: string;
  title: string;
};

export type ProfileCalendarDay = {
  dateKey: string;
  dayLabel: string;
  dayNumber: string;
  hasOutfit: boolean;
  isToday: boolean;
};

export function buildProfileDisplayName(profile: Profile | null, email?: string | null) {
  const displayName = profile?.display_name?.trim();
  if (displayName) {
    return displayName;
  }

  const username = profile?.username?.trim();
  if (username) {
    return username;
  }

  const emailPrefix = email?.split("@")[0]?.split(/[._-]/)[0]?.trim();
  if (emailPrefix) {
    return emailPrefix.charAt(0).toUpperCase() + emailPrefix.slice(1);
  }

  return "Your wardrobe";
}

export function buildProfileInitials(name: string) {
  const segments = name.split(/[\s._@-]+/).filter(Boolean);
  if (segments.length === 0) {
    return "T";
  }

  return segments
    .slice(0, 2)
    .map((segment) => segment.charAt(0).toUpperCase())
    .join("");
}

export function buildProfileDescriptor(
  profile: Profile | null,
  insights: ClosetInsightsSnapshot
) {
  const bio = profile?.bio?.trim();
  if (bio) {
    return bio;
  }

  if (insights.topColor && insights.topCategory) {
    return `${insights.topColor.label} tones and ${insights.topCategory.label.toLowerCase()} are shaping the closet signature.`;
  }

  if (insights.topCategory) {
    return `${insights.topCategory.label} currently leads the wardrobe.`;
  }

  return "Building a sharper personal wardrobe system.";
}

export function buildProfileCompletion(profile: Profile | null) {
  const fields = [profile?.username, profile?.display_name, profile?.bio];
  const completed = fields.filter((field) => Boolean(field?.trim())).length;
  return Math.round((completed / fields.length) * 100);
}

export function buildRecentProfileLooks(
  outfits: Record<string, OutfitEntry>,
  limit = 5
): ProfileRecentLook[] {
  return Object.entries(outfits)
    .sort(([left], [right]) => right.localeCompare(left))
    .slice(0, limit)
    .map(([outfitDate, outfit]) => {
      const date = new Date(`${outfitDate}T12:00:00`);
      return {
        dateKey: outfitDate,
        image: outfit.imageUri ? { uri: outfit.imageUri } : outfit.image,
        itemCount: outfit.items.length,
        note: outfit.note ?? null,
        subtitle: formatFullDate(date),
        title: outfit.occasion ?? formatDayName(date)
      };
    });
}

export function buildProfileCalendarDays(
  outfits: Record<string, OutfitEntry>,
  totalDays = 14
): ProfileCalendarDay[] {
  return Array.from({ length: totalDays }, (_, index) => {
    const date = new Date();
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() - (totalDays - 1 - index));
    const key = dateKey(date);

    return {
      dateKey: key,
      dayLabel: formatDayName(date).slice(0, 3),
      dayNumber: `${date.getDate()}`,
      hasOutfit: Boolean(outfits[key]),
      isToday: key === dateKey(new Date())
    };
  });
}

export function buildProfileSavedEntries(entries: LookbookEntry[], limit = 4) {
  return entries.slice(0, limit).map((entry) => ({
    id: entry.id,
    image: entry.image,
    meta: entry.items > 0 ? `${entry.date} · ${entry.items} items` : entry.date,
    route: `/lookbook/${entry.id}`,
    title: entry.context,
    type: entry.type
  }));
}
