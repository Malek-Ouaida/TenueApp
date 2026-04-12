import { compactList, humanizeEnum } from "../lib/format";
import type {
  ClosetBrowseFilters,
  ClosetBrowseListItemSnapshot,
  ClosetDraftSnapshot,
  ClosetFieldCanonicalValue,
  ClosetItemDetailSnapshot,
  ClosetReviewFieldSnapshot,
  ClosetItemReviewSnapshot,
  ClosetMetadataProjectionSnapshot,
  ClosetProcessingImageSnapshot,
  ClosetProcessingSnapshot,
  ClosetQueueSection,
  ClosetQueueSectionKey,
  ClosetRetryStep
} from "./types";

export const CLOSET_FIELD_ORDER = [
  "title",
  "category",
  "subcategory",
  "primary_color",
  "secondary_colors",
  "material",
  "pattern",
  "brand",
  "style_tags",
  "fit_tags",
  "occasion_tags",
  "season_tags",
  "silhouette",
  "attributes",
  "formality",
  "warmth",
  "coverage",
  "statement_level",
  "versatility"
] as const;

export function resolvePreferredImage(
  images: Array<ClosetProcessingImageSnapshot | null | undefined>
): ClosetProcessingImageSnapshot | null {
  return images.find((image) => Boolean(image?.url)) ?? null;
}

export function getDraftPrimaryImage(item: ClosetDraftSnapshot) {
  return item.original_images.find((image) => image.is_primary) ?? item.original_images[0] ?? null;
}

export function getConfirmedItemPreview(
  item: ClosetBrowseListItemSnapshot | ClosetItemDetailSnapshot
) {
  return resolvePreferredImage([
    item.display_image,
    item.thumbnail_image,
    "original_image" in item ? item.original_image : null
  ]);
}

export function getReviewItemPreview(item: ClosetItemReviewSnapshot | ClosetProcessingSnapshot) {
  return resolvePreferredImage([
    item.display_image,
    item.thumbnail_image,
    item.original_image
  ]);
}

export function getQueueSectionKey(item: ClosetDraftSnapshot): ClosetQueueSectionKey {
  if (
    item.processing_status === "pending" ||
    item.processing_status === "running" ||
    item.lifecycle_status === "processing"
  ) {
    return "processing";
  }

  if (item.failure_summary || item.processing_status === "failed") {
    return "needs_attention";
  }

  return "needs_review";
}

export function buildQueueSections(items: ClosetDraftSnapshot[]): ClosetQueueSection[] {
  const byKey: Record<ClosetQueueSectionKey, ClosetDraftSnapshot[]> = {
    needs_review: [],
    processing: [],
    needs_attention: []
  };

  for (const item of items) {
    byKey[getQueueSectionKey(item)].push(item);
  }

  const sections: ClosetQueueSection[] = [
    {
      key: "needs_review",
      title: "Needs review",
      items: byKey.needs_review
    },
    {
      key: "processing",
      title: "Processing",
      items: byKey.processing
    },
    {
      key: "needs_attention",
      title: "Needs attention",
      items: byKey.needs_attention
    }
  ];

  return sections.filter((section) => section.items.length > 0);
}

export function isReviewableDraft(item: ClosetDraftSnapshot) {
  return item.lifecycle_status !== "archived" && getQueueSectionKey(item) === "needs_review";
}

export function getStatusChipTone(status: string) {
  if (status === "confirmed" || status === "ready_to_confirm" || status === "completed") {
    return "success" as const;
  }
  if (status === "pending" || status === "running" || status === "processing") {
    return "warning" as const;
  }
  if (status === "failed" || status === "needs_review") {
    return "danger" as const;
  }
  return "muted" as const;
}

export function getRetryStepLabel(step: ClosetRetryStep | null | undefined) {
  switch (step) {
    case "image_processing":
      return "Retry image cleanup";
    case "metadata_extraction":
      return "Retry AI suggestions";
    case "normalization_projection":
      return "Retry normalization";
    default:
      return "Retry";
  }
}

export function formatFieldValue(value: ClosetFieldCanonicalValue): string | null {
  if (typeof value === "string") {
    return value;
  }

  if (Array.isArray(value)) {
    return compactList(value);
  }

  return null;
}

export function buildProjectionMeta(
  projection: ClosetMetadataProjectionSnapshot | null | undefined
): string | null {
  if (!projection) {
    return null;
  }

  return compactList(
    [
      projection.category,
      projection.subcategory,
      projection.primary_color,
      projection.material,
      projection.brand
    ].filter((value): value is string => Boolean(value))
  );
}

export function buildBrowseMeta(item: ClosetBrowseListItemSnapshot): string | null {
  return compactList(
    [
      item.category,
      item.subcategory,
      item.primary_color,
      item.material,
      item.brand
    ].filter((value): value is string => Boolean(value))
  );
}

export function buildClosetFilterSummary(filters: ClosetBrowseFilters): string | null {
  return compactList(
    [
      filters.category,
      filters.subcategory,
      filters.color,
      filters.material,
      filters.pattern
    ].filter((value): value is string => Boolean(value))
  );
}

export function getReviewRail(
  review: ClosetItemReviewSnapshot | null,
  processing: ClosetProcessingSnapshot | null
) {
  const processingStatus = review?.processing_status ?? processing?.processing_status ?? "pending";
  const extractionStatus = review?.extraction_status ?? "pending";
  const normalizationStatus = review?.normalization_status ?? "pending";
  const reviewStatus = review?.review_status ?? "needs_review";

  return [
    {
      key: "upload",
      label: "Upload",
      status: processing ? "completed" : "pending"
    },
    {
      key: "cleanup",
      label: "Image cleanup",
      status: processingStatus
    },
    {
      key: "suggest",
      label: "AI suggestion",
      status:
        extractionStatus === "completed" && normalizationStatus === "completed"
          ? "completed"
          : extractionStatus === "failed" || normalizationStatus === "failed"
            ? "failed"
            : extractionStatus === "pending" || extractionStatus === "running"
              ? extractionStatus
              : normalizationStatus
    },
    {
      key: "confirm",
      label: "Confirm",
      status: reviewStatus
    }
  ];
}

export function humanizeStatus(status: string | null | undefined) {
  return humanizeEnum(status);
}

export function formatConfidence(confidence: number | null | undefined): string | null {
  if (confidence == null) {
    return null;
  }

  return `${Math.round(confidence * 100)}% confidence`;
}

export function getReviewFieldStateLabel(field: ClosetReviewFieldSnapshot) {
  if (field.current_state.applicability_state === "not_applicable") {
    return "Not applicable";
  }

  if (field.current_state.review_state === "user_confirmed") {
    return "Confirmed";
  }

  if (field.current_state.review_state === "user_edited") {
    return "Edited";
  }

  if (
    field.current_state.applicability_state === "unknown" ||
    field.current_state.review_state === "system_unset"
  ) {
    return "Unknown";
  }

  if (field.suggested_state || field.current_state.review_state === "pending_user") {
    return "Suggested";
  }

  return humanizeStatus(field.current_state.review_state);
}

export function getReviewFieldStateTone(field: ClosetReviewFieldSnapshot) {
  const label = getReviewFieldStateLabel(field);

  switch (label) {
    case "Confirmed":
      return "success" as const;
    case "Edited":
      return "organize" as const;
    case "Suggested":
      return "review" as const;
    case "Unknown":
    case "Not applicable":
      return "muted" as const;
    default:
      return "default" as const;
  }
}

export function buildReviewFieldHelper(field: ClosetReviewFieldSnapshot) {
  const pieces: string[] = [];
  const confidenceLabel = formatConfidence(
    field.suggested_state?.confidence ?? field.current_state.confidence
  );

  if (getReviewFieldStateLabel(field) === "Suggested") {
    pieces.push("AI suggestion");
  } else if (field.current_state.review_state === "user_confirmed") {
    pieces.push("User confirmed");
  } else if (field.current_state.review_state === "user_edited") {
    pieces.push("User edited");
  }

  if (confidenceLabel) {
    pieces.push(confidenceLabel);
  }

  return pieces.join(" · ") || null;
}
