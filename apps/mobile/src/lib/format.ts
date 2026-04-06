export function titleCase(value: string): string {
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function humanizeEnum(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }

  return titleCase(value.replaceAll("_", " "));
}

export function formatRelativeDate(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }

  const date = new Date(value);
  const minutes = Math.round((date.getTime() - Date.now()) / (1000 * 60));
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

  if (Math.abs(minutes) < 60) {
    return formatter.format(minutes, "minute");
  }

  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) {
    return formatter.format(hours, "hour");
  }

  const days = Math.round(hours / 24);
  if (Math.abs(days) < 7) {
    return formatter.format(days, "day");
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric"
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

export function formatScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function compactList(values: string[] | null | undefined): string | null {
  if (!values?.length) {
    return null;
  }

  return values.join(" · ");
}
