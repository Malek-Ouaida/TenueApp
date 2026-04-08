import { LookbookPage } from "@/components/companion/LookbookPage";
import { ApiError } from "@/lib/api";
import { formatDisplayDate, getDaysAgo, getPrimaryImageUrl } from "@/lib/companion-ui";
import { listFlattenedLookbookEntries } from "@/lib/lookbook";
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

function buildContext(entry: Awaited<ReturnType<typeof listFlattenedLookbookEntries>>[number]) {
  if (entry.entry.caption) {
    return entry.entry.caption;
  }

  if (entry.entry.note_text) {
    return entry.entry.note_text.length > 34
      ? `${entry.entry.note_text.slice(0, 31)}...`
      : entry.entry.note_text;
  }

  if (entry.entry.outfit?.title) {
    return entry.entry.outfit.title;
  }

  return entry.lookbook_title;
}

async function listLookbookEntries(accessToken: string) {
  try {
    return await listFlattenedLookbookEntries(accessToken);
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
  const entries = await listLookbookEntries(session.session.access_token);

  return (
    <LookbookPage
      entries={entries.map((entry) => ({
        id: entry.entry.id,
        imageUrl: getPrimaryImageUrl(entry.entry.image, entry.entry.outfit?.cover_image, entry.lookbook_cover_image),
        type: entry.entry.entry_type === "outfit" ? "outfit" : "inspiration",
        dateLabel: formatEntryDate(entry.entry.updated_at),
        context: buildContext(entry),
        items: entry.entry.outfit?.item_count ?? 0,
        isNote: entry.entry.entry_type === "note"
      }))}
    />
  );
}
