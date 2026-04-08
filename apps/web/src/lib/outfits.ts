import { apiRequest } from "./api";
import type { ClosetProcessingImage } from "./closet";

export type OutfitItem = {
  closet_item_id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  display_image: ClosetProcessingImage | null;
  thumbnail_image: ClosetProcessingImage | null;
  role: string | null;
  layer_index: number | null;
  sort_index: number;
  is_optional: boolean;
};

export type OutfitDetail = {
  id: string;
  title: string | null;
  notes: string | null;
  occasion: string | null;
  season: string | null;
  source: string;
  item_count: number;
  is_favorite: boolean;
  is_archived: boolean;
  cover_image: ClosetProcessingImage | null;
  items: OutfitItem[];
  created_at: string;
  updated_at: string;
};

export async function getOutfitDetail(accessToken: string, outfitId: string) {
  return apiRequest<OutfitDetail>(`/outfits/${outfitId}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`
    },
    ttlSeconds: 10
  });
}
