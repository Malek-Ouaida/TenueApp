import { notFound } from "next/navigation";

import { LookbookEntryDetail } from "@/components/companion/LookbookEntryDetail";
import { ApiError } from "@/lib/api";
import { formatDisplayDate, getPrimaryImageUrl } from "@/lib/companion-ui";
import { getFlattenedLookbookEntry } from "@/lib/lookbook";
import { getOutfitDetail } from "@/lib/outfits";
import { requireSession } from "../../../../lib/auth/session";

type LookbookDetailPageProps = {
  params: Promise<{
    id: string;
  }>;
};

async function getLookbookEntryOrNotFound(accessToken: string, entryId: string) {
  try {
    return await getFlattenedLookbookEntry(accessToken, entryId);
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

  const outfitDetail = entry.entry.outfit ? await getOutfitDetail(accessToken, entry.entry.outfit.id) : null;
  const title =
    entry.entry.caption ??
    entry.entry.outfit?.title ??
    (entry.entry.note_text
      ? entry.entry.note_text.length > 48
        ? `${entry.entry.note_text.slice(0, 45)}...`
        : entry.entry.note_text
      : entry.lookbook_title);
  const notes =
    entry.entry.note_text ??
    entry.entry.caption ??
    outfitDetail?.notes ??
    entry.lookbook_description ??
    "Saved to your lookbook.";

  return (
    <LookbookEntryDetail
      backHref="/lookbook"
      imageUrl={getPrimaryImageUrl(entry.entry.image, entry.entry.outfit?.cover_image, entry.lookbook_cover_image)}
      title={title}
      dateLabel={formatDisplayDate(entry.entry.updated_at)}
      itemCount={outfitDetail?.items.length ?? entry.entry.outfit?.item_count ?? 0}
      notes={notes}
      items={
        outfitDetail?.items.map((item) => ({
          id: item.closet_item_id,
          title: item.title ?? "Closet Item",
          imageUrl: getPrimaryImageUrl(item.display_image, item.thumbnail_image)
        })) ?? []
      }
    />
  );
}
