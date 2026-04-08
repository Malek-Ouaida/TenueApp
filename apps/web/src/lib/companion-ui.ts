export const CATEGORY_LABELS: Record<string, string> = {
  tops: "Tops",
  bottoms: "Bottoms",
  dresses: "Dresses",
  outerwear: "Outerwear",
  shoes: "Shoes",
  bags: "Bags",
  accessories: "Accessories"
};

export function formatDaysAgo(days: number | null) {
  if (days === null) {
    return "Not worn yet";
  }

  if (days === 0) {
    return "Today";
  }

  if (days === 1) {
    return "Yesterday";
  }

  if (days < 7) {
    return `${days} days ago`;
  }

  if (days < 30) {
    return `${Math.floor(days / 7)} weeks ago`;
  }

  return `${Math.floor(days / 30)} months ago`;
}

export function formatCompactDaysAgo(days: number | null) {
  if (days === null) {
    return "never";
  }

  if (days === 0) {
    return "today";
  }

  if (days === 1) {
    return "1d ago";
  }

  if (days < 7) {
    return `${days}d ago`;
  }

  if (days < 30) {
    return `${Math.floor(days / 7)}w ago`;
  }

  return `${Math.floor(days / 30)}mo ago`;
}

export function getDaysAgo(value: string | null | undefined, referenceDate = new Date()) {
  if (!value) {
    return null;
  }

  const target = new Date(value);
  const difference = referenceDate.getTime() - target.getTime();

  if (Number.isNaN(difference)) {
    return null;
  }

  return Math.max(0, Math.floor(difference / (1000 * 60 * 60 * 24)));
}

export function formatDisplayDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric"
  }).format(new Date(value));
}

export function formatMonthYear(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric"
  }).format(new Date(value));
}

export function humanizeValue(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

export function getPrimaryImageUrl(
  ...images: Array<{ url: string } | null | undefined>
) {
  return images.find((image) => image?.url)?.url ?? null;
}

export function findFieldValue(
  fieldStates: Array<{ field_name: string; canonical_value: unknown }>,
  fieldName: string
) {
  const match = fieldStates.find((field) => field.field_name === fieldName);
  if (!match) {
    return null;
  }

  return normalizeFieldValue(match.canonical_value);
}

function normalizeFieldValue(value: unknown): string | null {
  if (Array.isArray(value)) {
    const normalized = value
      .map((entry) => normalizeFieldValue(entry))
      .filter((entry): entry is string => Boolean(entry));

    return normalized.length > 0 ? normalized.join(", ") : null;
  }

  if (typeof value === "string") {
    return humanizeValue(value) ?? value;
  }

  if (typeof value === "number") {
    return String(value);
  }

  return null;
}
