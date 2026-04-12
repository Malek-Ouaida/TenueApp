import Link from "next/link";
import { notFound } from "next/navigation";
import { AlertCircle, ArrowLeft } from "lucide-react";

import { ApiError } from "@/lib/api";
import { getClosetItemDetail, getSimilarClosetItems } from "@/lib/closet";
import {
  CATEGORY_LABELS,
  formatDaysAgo,
  getDaysAgo,
  getPrimaryImageUrl,
  humanizeValue
} from "@/lib/companion-ui";
import { listAllInsightItemUsage } from "@/lib/insights";
import { requireSession } from "../../../../lib/auth/session";

type ItemDetailPageProps = {
  params: Promise<{
    id: string;
  }>;
};

function formatValueList(values: string[] | null | undefined) {
  return values?.map((value) => humanizeValue(value) ?? value).join(", ") || "Not set";
}

async function getClosetItemOrNotFound(accessToken: string, itemId: string) {
  try {
    return await getClosetItemDetail(accessToken, itemId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }

    throw error;
  }
}

export default async function ItemDetailPage({ params }: ItemDetailPageProps) {
  const { id } = await params;
  const session = await requireSession();
  const accessToken = session.session.access_token;

  try {
    const item = await getClosetItemOrNotFound(accessToken, id);
    const [similarResult, usageResult] = await Promise.allSettled([
      getSimilarClosetItems(accessToken, id),
      listAllInsightItemUsage(accessToken)
    ]);
    const similarItems = similarResult.status === "fulfilled" ? similarResult.value : [];
    const usageItems = usageResult.status === "fulfilled" ? usageResult.value : [];
    const usageUnavailable = usageResult.status === "rejected";
    const similarUnavailable = similarResult.status === "rejected";

    const usage = usageItems.find((entry) => entry.closet_item_id === item.item_id);
    const addedDaysAgo = getDaysAgo(item.confirmed_at);
    const lastWornDaysAgo = getDaysAgo(usage?.last_worn_date);
    const category = item.metadata_projection.category ?? "accessories";
    const title =
      item.metadata_projection.title ??
      humanizeValue(item.metadata_projection.subcategory) ??
      "Closet Item";
    const imageUrl = getPrimaryImageUrl(
      item.display_image,
      item.thumbnail_image,
      item.original_image,
      ...item.original_images
    );
    const fields = [
      { label: "Category", value: CATEGORY_LABELS[category] ?? humanizeValue(category) ?? category },
      {
        label: "Type",
        value: humanizeValue(item.metadata_projection.subcategory) ?? "Not set"
      },
      {
        label: "Color",
        value: humanizeValue(item.metadata_projection.primary_color) ?? "Not set"
      },
      {
        label: "Additional colors",
        value: formatValueList(item.metadata_projection.secondary_colors)
      },
      {
        label: "Material",
        value: humanizeValue(item.metadata_projection.material) ?? "Not set"
      },
      {
        label: "Pattern",
        value: humanizeValue(item.metadata_projection.pattern) ?? "Not set"
      },
      {
        label: "Season",
        value: formatValueList(item.metadata_projection.season_tags)
      },
      {
        label: "Occasion",
        value: formatValueList(item.metadata_projection.occasion_tags)
      },
      {
        label: "Style",
        value: formatValueList(item.metadata_projection.style_tags)
      },
      {
        label: "Fit",
        value: formatValueList(item.metadata_projection.fit_tags)
      },
      {
        label: "Silhouette",
        value: humanizeValue(item.metadata_projection.silhouette) ?? "Not set"
      },
      {
        label: "Attributes",
        value: formatValueList(item.metadata_projection.attributes)
      }
    ];

    return (
      <div className="page-enter">
        <Link
          href="/closet"
          className="mb-6 inline-flex items-center gap-2 font-body text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back to closet
        </Link>

        <div className="grid gap-8 md:grid-cols-2">
          <div className="aspect-[4/5] overflow-hidden rounded-3xl bg-secondary" style={{ boxShadow: "var(--shadow-lg)" }}>
            {imageUrl ? (
              <img src={imageUrl} alt={title} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center px-6 text-center">
                <span className="font-display text-2xl font-semibold text-muted-foreground">{title}</span>
              </div>
            )}
          </div>

          <div className="space-y-8">
            <div>
              <h1 className="mb-1.5 font-display text-3xl font-semibold tracking-editorial text-foreground">{title}</h1>
              <p className="font-body text-sm text-muted-foreground">
                Added {formatDaysAgo(addedDaysAgo)} ·{" "}
                {item.metadata_projection.brand ?? "Brand not set"}
              </p>
            </div>

            <div>
              <h2 className="mb-3 font-body text-xs font-medium uppercase tracking-widest text-muted-foreground">
                Details
              </h2>
              <div className="overflow-hidden rounded-2xl bg-card" style={{ boxShadow: "var(--shadow-sm)" }}>
                {fields.map((field, index) => (
                  <div key={field.label} className="relative flex items-center justify-between gap-5 px-5 py-3.5">
                    <span className="font-body text-sm text-muted-foreground">{field.label}</span>
                    <span className="text-right font-body text-sm font-semibold text-foreground">{field.value}</span>
                    {index < fields.length - 1 ? <div className="absolute bottom-0 left-5 right-5 h-px bg-border" /> : null}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h2 className="mb-3 font-body text-xs font-medium uppercase tracking-widest text-muted-foreground">
                Usage
              </h2>
              <div className="rounded-2xl bg-card p-5" style={{ boxShadow: "var(--shadow-sm)" }}>
                <div className="flex items-center gap-6">
                  <div className="flex-1">
                    <p className="mb-1 font-body text-3xl font-bold leading-none text-foreground">
                      {usage?.wear_count ?? 0}
                    </p>
                    <p className="font-body text-sm text-muted-foreground">times worn</p>
                  </div>
                  <div className="h-10 w-px bg-border" />
                  <div className="flex-1">
                    <p className="mb-1 font-body text-base font-semibold text-foreground">
                      {formatDaysAgo(lastWornDaysAgo)}
                    </p>
                    <p className="font-body text-sm text-muted-foreground">last worn</p>
                  </div>
                </div>
                <div className="mt-5 border-t border-border pt-4">
                  <p className="mb-2.5 font-body text-xs uppercase tracking-widest text-muted-foreground">
                    Frequency
                  </p>
                  <div className="flex items-center gap-1">
                    {Array.from({ length: 12 }).map((_, index) => {
                      const activeCount = Math.min(12, Math.round((usage?.wear_count ?? 0) / 3));

                      return (
                        <div
                          key={index}
                          className="h-2 flex-1 rounded-full transition-all"
                          style={{
                            backgroundColor:
                              index < activeCount ? "hsl(var(--foreground))" : "hsl(var(--muted))",
                            opacity: index < activeCount ? 1 - index * 0.06 : 0.5
                          }}
                        />
                      );
                    })}
                  </div>
                </div>
                {usageUnavailable ? (
                  <p className="mt-4 border-t border-border pt-4 font-body text-sm text-muted-foreground">
                    Usage insights are temporarily unavailable.
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        {similarItems.length > 0 ? (
          <div className="mt-12">
            <h2 className="mb-4 font-display text-2xl font-semibold tracking-editorial text-foreground">
              Similar Items
            </h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {similarItems.map((similar) => {
                const similarTitle =
                  similar.other_item.title ??
                  humanizeValue(similar.other_item.subcategory) ??
                  "Closet Item";
                const similarImageUrl = getPrimaryImageUrl(
                  similar.other_item.display_image,
                  similar.other_item.thumbnail_image
                );

                return (
                  <Link
                    key={similar.edge_id}
                    href={`/closet/${similar.other_item.item_id}`}
                    className="card-lift rounded-2xl bg-card p-3"
                    style={{ boxShadow: "var(--shadow-sm)" }}
                  >
                    <div className="mb-2 aspect-[3/4] overflow-hidden rounded-xl bg-secondary">
                      {similarImageUrl ? (
                        <img
                          src={similarImageUrl}
                          alt={similarTitle}
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center px-4 text-center">
                          <span className="font-display text-base font-semibold text-muted-foreground">
                            {similarTitle}
                          </span>
                        </div>
                      )}
                    </div>
                    <p className="truncate font-body text-sm font-medium text-foreground">{similarTitle}</p>
                  </Link>
                );
              })}
            </div>
          </div>
        ) : similarUnavailable ? (
          <div className="mt-12 rounded-2xl border border-border bg-card px-5 py-4" style={{ boxShadow: "var(--shadow-sm)" }}>
            <p className="font-body text-sm text-muted-foreground">
              Similar-item suggestions are temporarily unavailable.
            </p>
          </div>
        ) : null}
      </div>
    );
  } catch (error) {
    if (error instanceof ApiError) {
      return (
        <div className="page-enter">
          <Link
            href="/closet"
            className="mb-6 inline-flex items-center gap-2 font-body text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> Back to closet
          </Link>

          <div
            className="rounded-3xl border border-border bg-card px-6 py-10 text-center"
            style={{ boxShadow: "var(--shadow-sm)" }}
          >
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
              <AlertCircle className="h-5 w-5 text-foreground" />
            </div>
            <h1 className="mb-2 font-display text-2xl font-semibold tracking-editorial text-foreground">
              Closet item unavailable
            </h1>
            <p className="mx-auto max-w-md font-body text-sm text-muted-foreground">
              {error.message}
            </p>
          </div>
        </div>
      );
    }

    throw error;
  }
}
