import type { ClosetBrowseListItemSnapshot, ClosetProcessingImageSnapshot, PresignedUploadDescriptor } from "../closet/types";
import type { WearItemRoleValue, WearLogDetailSnapshot } from "../wear/types";

export type LookbookSourceKindValue = "gallery_photo" | "wear_log";
export type LookbookIntentValue = "inspiration" | "recreate" | "logged";
export type LookbookStatusValue = "draft" | "published";

export type PrivateImageSnapshot = {
  asset_id: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  url: string;
  expires_at: string;
};

export type LookbookSourceSnapshot = {
  wear_log_id: string;
  wear_date: string;
  worn_at: string;
  context: string | null;
  vibe: string | null;
  notes: string | null;
  item_count: number;
  primary_image_asset_id: string | null;
  cover_image_asset_id: string | null;
};

export type LookbookOwnedOutfitSnapshot = {
  id: string;
  item_count: number;
  is_archived: boolean;
};

export type LookbookLinkedItemSnapshot = {
  closet_item_id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  display_image: ClosetProcessingImageSnapshot | null;
  thumbnail_image: ClosetProcessingImageSnapshot | null;
  role: string | null;
  sort_index: number;
};

export type LookbookEntrySummarySnapshot = {
  id: string;
  source_kind: LookbookSourceKindValue;
  intent: LookbookIntentValue;
  status: LookbookStatusValue;
  title: string | null;
  caption: string | null;
  notes: string | null;
  occasion_tag: string | null;
  season_tag: string | null;
  style_tag: string | null;
  primary_image: PrivateImageSnapshot | null;
  linked_item_count: number;
  has_linked_items: boolean;
  source_wear_log_id: string | null;
  owned_outfit: LookbookOwnedOutfitSnapshot | null;
  source_snapshot: LookbookSourceSnapshot | null;
  published_at: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LookbookEntryDetailSnapshot = LookbookEntrySummarySnapshot & {
  linked_items: LookbookLinkedItemSnapshot[];
};

export type LookbookEntryListResponse = {
  items: LookbookEntrySummarySnapshot[];
  next_cursor: string | null;
};

export type LookbookLinkedItemWriteRequest = {
  closet_item_id: string;
  role?: WearItemRoleValue | null;
  sort_index?: number | null;
};

export type GalleryLookbookEntryCreateRequest = {
  source_kind: "gallery_photo";
  intent: "inspiration" | "recreate";
  status: LookbookStatusValue;
  title?: string | null;
  caption?: string | null;
  notes?: string | null;
  occasion_tag?: string | null;
  season_tag?: string | null;
  style_tag?: string | null;
  primary_image_asset_id: string;
  linked_items?: LookbookLinkedItemWriteRequest[];
};

export type WearLogLookbookEntryCreateRequest = {
  source_kind: "wear_log";
  source_wear_log_id: string;
  intent?: "logged";
  status: LookbookStatusValue;
  title?: string | null;
  caption?: string | null;
  notes?: string | null;
  occasion_tag?: string | null;
  season_tag?: string | null;
  style_tag?: string | null;
};

export type LookbookEntryCreateRequest =
  | GalleryLookbookEntryCreateRequest
  | WearLogLookbookEntryCreateRequest;

export type LookbookEntryUpdateRequest = {
  title?: string | null;
  caption?: string | null;
  notes?: string | null;
  occasion_tag?: string | null;
  season_tag?: string | null;
  style_tag?: string | null;
  status?: LookbookStatusValue | null;
  primary_image_asset_id?: string | null;
  linked_items?: LookbookLinkedItemWriteRequest[] | null;
};

export type LookbookUploadIntentRequest = {
  filename: string;
  mime_type: string;
  file_size: number;
  sha256: string;
};

export type LookbookUploadIntentResponse = {
  upload_intent_id: string;
  expires_at: string;
  upload: PresignedUploadDescriptor;
};

export type LookbookWearLogCreateRequest = {
  wear_date?: string | null;
  worn_at?: string | null;
  timezone_name?: string | null;
  context?: string | null;
  notes?: string | null;
};

export type LookbookEntryFilters = {
  cursor?: string | null;
  limit?: number;
  status?: LookbookStatusValue | null;
  source_kind?: LookbookSourceKindValue | null;
  intent?: LookbookIntentValue | null;
  occasion_tag?: string | null;
  season_tag?: string | null;
  style_tag?: string | null;
  has_linked_items?: boolean | null;
  include_archived?: boolean;
};

export type LookbookSelectedItem = {
  closet_item_id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  image_url: string | null;
  role: WearItemRoleValue | null;
};

export function toLookbookSelectedItem(
  item: ClosetBrowseListItemSnapshot | LookbookLinkedItemSnapshot
): LookbookSelectedItem {
  return {
    closet_item_id: "item_id" in item ? item.item_id : item.closet_item_id,
    title: item.title,
    category: item.category,
    subcategory: item.subcategory,
    primary_color: item.primary_color,
    image_url: item.display_image?.url ?? item.thumbnail_image?.url ?? null,
    role: normalizeRole(("role" in item ? item.role : item.category) ?? null)
  };
}

export function normalizeRole(value: string | null | undefined): WearItemRoleValue | null {
  switch (value) {
    case "top":
    case "tops":
      return "top";
    case "bottom":
    case "bottoms":
      return "bottom";
    case "dress":
    case "dresses":
      return "dress";
    case "outerwear":
      return "outerwear";
    case "shoes":
      return "shoes";
    case "bag":
    case "bags":
      return "bag";
    case "accessory":
    case "accessories":
      return "accessory";
    case "other":
      return "other";
    default:
      return null;
  }
}

export function buildLookbookHeroUri(
  entry:
    | Pick<LookbookEntrySummarySnapshot, "primary_image" | "source_snapshot">
    | Pick<LookbookEntryDetailSnapshot, "primary_image" | "source_snapshot">
    | null
    | undefined,
  wearLog?: WearLogDetailSnapshot | null
) {
  return (
    entry?.primary_image?.url ??
    wearLog?.primary_photo?.url ??
    wearLog?.cover_image?.url ??
    wearLog?.items[0]?.display_image?.url ??
    wearLog?.items[0]?.thumbnail_image?.url ??
    null
  );
}
