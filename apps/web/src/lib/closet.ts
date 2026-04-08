import { apiRequest, buildApiPath, fetchAllCursorPages, type CursorPageResponse } from "./api";

export type ClosetProcessingImage = {
  asset_id: string;
  image_id: string | null;
  role: string;
  position: number | null;
  is_primary: boolean;
  mime_type: string;
  width: number | null;
  height: number | null;
  url: string;
  expires_at: string;
};

export type ClosetFieldState = {
  field_name: string;
  canonical_value: unknown;
  source: string;
  confidence: number | null;
  review_state: string;
  applicability_state: string;
  taxonomy_version: string;
  updated_at: string;
};

export type ClosetMetadataProjection = {
  taxonomy_version: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  secondary_colors: string[] | null;
  material: string | null;
  pattern: string | null;
  brand: string | null;
  style_tags: string[] | null;
  occasion_tags: string[] | null;
  season_tags: string[] | null;
  confirmed_at: string | null;
  updated_at: string;
};

export type ClosetBrowseListItem = {
  item_id: string;
  confirmed_at: string;
  updated_at: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  secondary_colors: string[] | null;
  material: string | null;
  pattern: string | null;
  brand: string | null;
  season_tags: string[] | null;
  display_image: ClosetProcessingImage | null;
  thumbnail_image: ClosetProcessingImage | null;
};

export type ClosetSimilarityListItem = {
  edge_id: string;
  label: string;
  similarity_type: string;
  decision_status: string;
  score: number;
  signals: Array<{
    code: string;
    label: string;
    contribution: number;
    metadata: Record<string, unknown> | null;
  }>;
  other_item: ClosetBrowseListItem;
};

export type ClosetItemDetail = {
  item_id: string;
  lifecycle_status: string;
  processing_status: string;
  review_status: string;
  failure_summary: string | null;
  confirmed_at: string;
  created_at: string;
  updated_at: string;
  display_image: ClosetProcessingImage | null;
  thumbnail_image: ClosetProcessingImage | null;
  original_image: ClosetProcessingImage | null;
  original_images: ClosetProcessingImage[];
  metadata_projection: ClosetMetadataProjection;
  field_states: ClosetFieldState[];
};

type ClosetBrowseListResponse = CursorPageResponse<ClosetBrowseListItem>;

type ClosetSimilarityListResponse = {
  item_id: string;
  similarity_status: string;
  latest_run: unknown;
  items: ClosetSimilarityListItem[];
};

function authHeaders(accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`
  };
}

export async function listAllClosetItems(accessToken: string) {
  return fetchAllCursorPages((cursor) =>
    apiRequest<ClosetBrowseListResponse>(buildApiPath("/closet/items", { cursor, limit: 50 }), {
      headers: authHeaders(accessToken),
      ttlSeconds: 10
    })
  );
}

export async function getClosetItemDetail(accessToken: string, itemId: string) {
  return apiRequest<ClosetItemDetail>(`/closet/items/${itemId}`, {
    headers: authHeaders(accessToken),
    ttlSeconds: 10
  });
}

export async function getSimilarClosetItems(accessToken: string, itemId: string, limit = 4) {
  const response = await apiRequest<ClosetSimilarityListResponse>(
    buildApiPath(`/closet/items/${itemId}/similar`, { limit }),
    {
      headers: authHeaders(accessToken),
      ttlSeconds: 10
    }
  );

  return response.items;
}
