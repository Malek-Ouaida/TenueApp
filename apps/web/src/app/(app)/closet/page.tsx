import { ClosetPage } from "@/components/companion/ClosetPage";
import { listAllClosetItems } from "@/lib/closet";
import {
  formatCompactDaysAgo,
  getDaysAgo,
  getPrimaryImageUrl,
  humanizeValue
} from "@/lib/companion-ui";
import { listAllInsightItemUsage } from "@/lib/insights";
import { requireSession } from "../../../lib/auth/session";

function buildClosetTag(args: {
  addedDaysAgo: number | null;
  lastWornDaysAgo: number | null;
  timesWorn: number;
  maxWearCount: number;
}) {
  if (args.timesWorn > 0 && args.timesWorn === args.maxWearCount) {
    return "Most worn";
  }

  if (args.addedDaysAgo !== null && args.addedDaysAgo <= 7) {
    return "Recently added";
  }

  if (args.lastWornDaysAgo !== null && args.lastWornDaysAgo <= 7) {
    return `Last worn ${formatCompactDaysAgo(args.lastWornDaysAgo)}`;
  }

  return null;
}

export default async function ClosetRoutePage() {
  const session = await requireSession();
  const accessToken = session.session.access_token;
  const [closetItems, itemUsage] = await Promise.all([
    listAllClosetItems(accessToken),
    listAllInsightItemUsage(accessToken)
  ]);

  const usageById = new Map(itemUsage.map((item) => [item.closet_item_id, item]));
  const maxWearCount = itemUsage.reduce((max, item) => Math.max(max, item.wear_count), 0);

  const items = closetItems.map((item) => {
    const usage = usageById.get(item.item_id);
    const addedDaysAgo = getDaysAgo(item.confirmed_at);
    const lastWornDaysAgo = getDaysAgo(usage?.last_worn_date);
    const category = item.category ?? "accessories";
    const categoryLabel = humanizeValue(category) ?? "Closet";

    return {
      id: item.item_id,
      title:
        item.title ??
        humanizeValue(item.subcategory) ??
        "Closet Item",
      category,
      categoryLabel,
      imageUrl: getPrimaryImageUrl(item.thumbnail_image, item.display_image),
      tag: buildClosetTag({
        addedDaysAgo,
        lastWornDaysAgo,
        timesWorn: usage?.wear_count ?? 0,
        maxWearCount
      }),
      color:
        humanizeValue(
          item.primary_color ?? usage?.primary_color ?? null
        ) ?? null,
      seasonTags: item.season_tags?.map((season) => humanizeValue(season) ?? season) ?? [],
      addedDaysAgo: addedDaysAgo ?? 0,
      timesWorn: usage?.wear_count ?? 0,
      lastWornDaysAgo
    };
  });

  return <ClosetPage items={items} />;
}
