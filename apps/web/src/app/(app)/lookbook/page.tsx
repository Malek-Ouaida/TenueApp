import { LookbookPage } from "@/components/companion/LookbookPage";
import { ApiError } from "@/lib/api";
import { formatDisplayDate, getDaysAgo, humanizeValue } from "@/lib/companion-ui";
import { listAllLookbookEntries } from "@/lib/lookbook";
import { requireSession } from "../../../lib/auth/session";

function formatEntryDate(value: string) {
  const daysAgo = getDaysAgo(value);

  if (daysAgo === 0) {
    return "Today";
  }

  if (daysAgo === 1) {
    return "Yesterday";
  }

  return formatDisplayDate(value);
}

function buildEntryTitle(entry: Awaited<ReturnType<typeof listAllLookbookEntries>>[number]) {
  if (entry.title) {
    return entry.title;
  }
  if (entry.caption) {
    return entry.caption.length > 40 ? `${entry.caption.slice(0, 37)}...` : entry.caption;
  }
  if (entry.source_kind === "wear_log" && entry.source_snapshot?.context) {
    return humanizeValue(entry.source_snapshot.context) ?? "Saved daily look";
  }
  return humanizeValue(entry.intent) ?? "Saved look";
}

async function loadLookbookEntries(accessToken: string) {
  try {
    return await listAllLookbookEntries(accessToken);
  } catch (error) {
    if (error instanceof ApiError) {
      console.error("Failed to load lookbook entries.", error);
      return [];
    }

    throw error;
  }
}

export default async function LookbookRoutePage() {
  const session = await requireSession();
  const entries = await loadLookbookEntries(session.session.access_token);

  return (
    <LookbookPage
      entries={entries.map((entry) => ({
        id: entry.id,
        imageUrl: entry.primary_image?.url ?? null,
        title: buildEntryTitle(entry),
        meta: [
          formatEntryDate(entry.published_at ?? entry.updated_at),
          entry.linked_item_count > 0 ? `${entry.linked_item_count} items` : null
        ]
          .filter(Boolean)
          .join(" · "),
        badgeLabel: humanizeValue(entry.status === "draft" ? "draft" : entry.intent) ?? "Saved",
        tags: [entry.occasion_tag, entry.season_tag, entry.style_tag]
          .map((value) => humanizeValue(value))
          .filter((value): value is string => Boolean(value)),
        tab:
          entry.status === "draft"
            ? "draft"
            : entry.intent === "logged"
              ? "logged"
              : entry.intent === "recreate"
                ? "recreate"
                : "inspiration"
      }))}
    />
  );
}
