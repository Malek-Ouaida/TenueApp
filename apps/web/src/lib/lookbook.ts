import { apiRequest, buildApiPath, fetchAllCursorPages, type CursorPageResponse } from "./api";

export type PrivateImage = {
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

export type LookbookOwnedOutfit = {
  id: string;
  item_count: number;
  is_archived: boolean;
};

export type LookbookLinkedItem = {
  closet_item_id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  display_image: PrivateImage | null;
  thumbnail_image: PrivateImage | null;
  role: string | null;
  sort_index: number;
};

export type LookbookEntrySummary = {
  id: string;
  source_kind: "gallery_photo" | "wear_log";
  intent: "inspiration" | "recreate" | "logged";
  status: "draft" | "published";
  title: string | null;
  caption: string | null;
  notes: string | null;
  occasion_tag: string | null;
  season_tag: string | null;
  style_tag: string | null;
  primary_image: PrivateImage | null;
  linked_item_count: number;
  has_linked_items: boolean;
  source_wear_log_id: string | null;
  owned_outfit: LookbookOwnedOutfit | null;
  source_snapshot: LookbookSourceSnapshot | null;
  published_at: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LookbookEntryDetail = LookbookEntrySummary & {
  linked_items: LookbookLinkedItem[];
};

type LookbookEntryListResponse = CursorPageResponse<LookbookEntrySummary>;

function authHeaders(accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`
  };
}

export async function listAllLookbookEntries(
  accessToken: string,
  filters: {
    status?: "draft" | "published";
    source_kind?: "gallery_photo" | "wear_log";
    intent?: "inspiration" | "recreate" | "logged";
    has_linked_items?: boolean;
    include_archived?: boolean;
  } = {}
) {
  return fetchAllCursorPages((cursor) =>
    apiRequest<LookbookEntryListResponse>(
      buildApiPath("/lookbook/entries", { ...filters, cursor, limit: 50 }),
      {
        headers: authHeaders(accessToken),
        ttlSeconds: 10
      }
    )
  );
}

export async function listRecentLookbookEntries(accessToken: string, limit = 6) {
  const response = await apiRequest<LookbookEntryListResponse>(
    buildApiPath("/lookbook/entries", { status: "published", limit }),
    {
      headers: authHeaders(accessToken),
      ttlSeconds: 10
    }
  );

  return response.items;
}

export async function getLookbookEntry(accessToken: string, entryId: string) {
  return apiRequest<LookbookEntryDetail>(`/lookbook/entries/${entryId}`, {
    headers: authHeaders(accessToken),
    ttlSeconds: 10
  });
}
