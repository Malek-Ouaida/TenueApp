import { compactList, humanizeEnum } from "../lib/format";

import type {
  ClosetFieldCanonicalValue,
  ClosetItemReviewSnapshot,
  ClosetMetadataOptionsResponse,
  ClosetReviewFieldChange,
  ClosetReviewFieldSnapshot
} from "./types";

export type ReviewFieldDescriptor = {
  confidence: "high" | "medium" | "low";
  field: ClosetReviewFieldSnapshot;
  label: string;
  options: string[];
  value: string;
  valueSelection: ClosetFieldCanonicalValue;
};

const PREFERRED_FIELD_ORDER = [
  "title",
  "category",
  "subcategory",
  "colors",
  "material",
  "pattern",
  "brand",
  "season_tags",
  "occasion_tags",
  "style_tags",
  "fit_tags",
  "silhouette",
  "attributes"
] as const;

export function hasCanonicalValue(value: ClosetFieldCanonicalValue) {
  if (value == null) {
    return false;
  }

  if (typeof value === "string") {
    return Boolean(value.trim());
  }

  if (Array.isArray(value)) {
    return value.length > 0;
  }

  return true;
}

export function isSuggestedUsable(field: ClosetReviewFieldSnapshot) {
  if (!field.suggested_state) {
    return false;
  }

  if (["unknown", "not_applicable"].includes(field.suggested_state.applicability_state)) {
    return true;
  }

  return hasCanonicalValue(field.suggested_state.canonical_value);
}

export function resolveFieldSelectionValue(field: ClosetReviewFieldSnapshot): ClosetFieldCanonicalValue {
  if (
    field.current_state.review_state === "user_confirmed" ||
    field.current_state.review_state === "user_edited" ||
    field.current_state.applicability_state === "not_applicable" ||
    hasCanonicalValue(field.current_state.canonical_value)
  ) {
    return field.current_state.canonical_value;
  }

  if (isSuggestedUsable(field)) {
    return field.suggested_state?.canonical_value ?? null;
  }

  return field.current_state.canonical_value;
}

export function asString(value: ClosetFieldCanonicalValue): string | null {
  return typeof value === "string" ? value : null;
}

export function asStringArray(value: ClosetFieldCanonicalValue): string[] {
  return Array.isArray(value) ? value : [];
}

export function fieldIsMultiValue(fieldName: string) {
  return ["colors", "style_tags", "fit_tags", "occasion_tags", "season_tags", "attributes"].includes(
    fieldName
  );
}

export function formatFieldValue(value: ClosetFieldCanonicalValue): string | null {
  if (typeof value === "string") {
    return humanizeEnum(value);
  }

  if (Array.isArray(value)) {
    return compactList(value.map(humanizeEnum));
  }

  return null;
}

function getFieldLabel(fieldName: string) {
  switch (fieldName) {
    case "subcategory":
      return "Subcategory";
    case "style_tags":
      return "Style";
    case "occasion_tags":
      return "Occasion";
    case "season_tags":
      return "Season";
    case "colors":
      return "Color";
    case "fit_tags":
      return "Fit";
    case "attributes":
      return "Attributes";
    default:
      return humanizeEnum(fieldName);
  }
}

function getConfidenceTone(confidence: number | null | undefined): ReviewFieldDescriptor["confidence"] {
  if ((confidence ?? 0) >= 0.8) {
    return "high";
  }

  if ((confidence ?? 0) >= 0.55) {
    return "medium";
  }

  return "low";
}

export function selectionOptionsForField(
  fieldName: string,
  metadata: ClosetMetadataOptionsResponse | null,
  currentCategory: string | null
) {
  if (!metadata) {
    return [];
  }

  switch (fieldName) {
    case "category":
      return metadata.categories.map((entry) => entry.name);
    case "subcategory": {
      const preferredOptions = currentCategory
        ? metadata.categories.find((entry) => entry.name === currentCategory)?.subcategories ?? []
        : [];
      const allOptions = metadata.categories.flatMap((entry) => entry.subcategories);
      return Array.from(new Set(preferredOptions.concat(allOptions)));
    }
    case "colors":
      return metadata.colors;
    case "material":
      return metadata.materials;
    case "pattern":
      return metadata.patterns;
    case "style_tags":
      return metadata.style_tags;
    case "fit_tags":
      return metadata.fit_tags;
    case "occasion_tags":
      return metadata.occasion_tags;
    case "season_tags":
      return metadata.season_tags;
    case "silhouette":
      return metadata.silhouettes;
    case "attributes":
      return metadata.attributes;
    default:
      return [];
  }
}

function describeSelectionValue(field: ClosetReviewFieldSnapshot, selectionValue: ClosetFieldCanonicalValue) {
  if (field.current_state.applicability_state === "not_applicable") {
    return "Not applicable";
  }

  if (field.current_state.applicability_state === "unknown" && !isSuggestedUsable(field)) {
    return "Unknown";
  }

  return (
    formatFieldValue(selectionValue) ??
    formatFieldValue(field.suggested_state?.canonical_value ?? null) ??
    "Needs review"
  );
}

export function buildAutoAcceptChanges(review: ClosetItemReviewSnapshot | null | undefined) {
  if (!review) {
    return [] as ClosetReviewFieldChange[];
  }

  return review.review_fields
    .filter(
      (field) =>
        isSuggestedUsable(field) &&
        !["user_confirmed", "user_edited"].includes(field.current_state.review_state)
    )
    .map((field) => ({
      field_name: field.field_name,
      operation: "accept_suggestion" as const
    }));
}

export function buildReviewFieldDescriptors(
  review: ClosetItemReviewSnapshot | null | undefined,
  metadata: ClosetMetadataOptionsResponse | null | undefined
) {
  if (!review) {
    return [] as ReviewFieldDescriptor[];
  }

  const preferredFields = PREFERRED_FIELD_ORDER.map((fieldName) =>
    review.review_fields.find((field) => field.field_name === fieldName)
  ).filter((field): field is ClosetReviewFieldSnapshot => Boolean(field));

  const additionalFields = review.review_fields.filter(
    (field) => field.field_name !== "title" && !PREFERRED_FIELD_ORDER.includes(field.field_name as never)
  );

  const orderedFields = preferredFields.concat(additionalFields);
  const categoryField = review.review_fields.find((field) => field.field_name === "category");
  const currentCategory = categoryField
    ? asString(resolveFieldSelectionValue(categoryField)) ??
      asString(categoryField.suggested_state?.canonical_value ?? null)
    : null;

  return orderedFields.map((field) => {
    const selectionValue = resolveFieldSelectionValue(field);

    return {
      confidence: getConfidenceTone(field.suggested_state?.confidence ?? field.current_state.confidence),
      field,
      label: getFieldLabel(field.field_name),
      options: selectionOptionsForField(field.field_name, metadata ?? null, currentCategory),
      value: describeSelectionValue(field, selectionValue),
      valueSelection: selectionValue
    };
  });
}
