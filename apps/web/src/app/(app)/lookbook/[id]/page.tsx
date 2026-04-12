import { notFound } from "next/navigation";

import { LookbookEntryDetail } from "@/components/companion/LookbookEntryDetail";
import { ApiError } from "@/lib/api";
import { formatDisplayDate, humanizeValue } from "@/lib/companion-ui";
import { getLookbookEntry } from "@/lib/lookbook";
import { requireSession } from "../../../../lib/auth/session";

type LookbookDetailPageProps = {
  params: Promise<{
    id: string;
  }>;
};

async function getLookbookEntryOrNotFound(accessToken: string, entryId: string) {
  try {
    return await getLookbookEntry(accessToken, entryId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }
}

export default async function LookbookDetailPage({ params }: LookbookDetailPageProps) {
  const { id } = await params;
  const session = await requireSession();
  const accessToken = session.session.access_token;
  const entry = await getLookbookEntryOrNotFound(accessToken, id);

  const title =
    entry.title ??
    entry.caption ??
    (entry.source_kind === "wear_log" && entry.source_snapshot?.context
      ? humanizeValue(entry.source_snapshot.context)
      : humanizeValue(entry.intent)) ??
    "Saved look";
  const subtitle =
    entry.source_kind === "wear_log"
      ? "Saved from a confirmed daily log."
      : entry.intent === "recreate"
        ? "A gallery look you want to rebuild."
        : "A gallery look saved for inspiration.";
  const sourceMeta =
    entry.source_kind === "wear_log" && entry.source_snapshot
      ? `Saved from daily log on ${formatDisplayDate(`${entry.source_snapshot.wear_date}T12:00:00Z`)}`
      : null;
  const statusLabel = entry.archived_at
    ? "Archived"
    : (humanizeValue(entry.status) ?? "Saved");

  return (
    <LookbookEntryDetail
      backHref="/lookbook"
      imageUrl={entry.primary_image?.url ?? null}
      title={title}
      subtitle={subtitle}
      badgeLabel={humanizeValue(entry.intent) ?? "Saved look"}
      statusLabel={statusLabel}
      dateLabel={formatDisplayDate(entry.published_at ?? entry.updated_at)}
      caption={entry.caption}
      notes={entry.notes ?? entry.source_snapshot?.notes ?? null}
      tags={[entry.occasion_tag, entry.season_tag, entry.style_tag]
        .map((value) => humanizeValue(value))
        .filter((value): value is string => Boolean(value))}
      itemCount={entry.linked_item_count}
      sourceMeta={sourceMeta}
      canWearThisLook={entry.has_linked_items}
      items={entry.linked_items.map((item) => ({
        id: item.closet_item_id,
        title: item.title ?? "Closet Item",
        imageUrl: item.display_image?.url ?? item.thumbnail_image?.url ?? null,
        meta: [item.primary_color, humanizeValue(item.subcategory ?? item.category ?? item.role)]
          .filter(Boolean)
          .join(" · ")
      }))}
    />
  );
}
