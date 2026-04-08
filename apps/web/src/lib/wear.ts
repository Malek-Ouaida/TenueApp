import { apiRequest, buildApiPath, fetchAllCursorPages, type CursorPageResponse } from "./api";
import type { ClosetProcessingImage } from "./closet";

export type WearLogTimelineItem = {
  id: string;
  wear_date: string;
  context: string | null;
  item_count: number;
  source: string;
  is_confirmed: boolean;
  cover_image: ClosetProcessingImage | null;
  outfit_title: string | null;
  created_at: string;
  updated_at: string;
};

type WearLogTimelineResponse = CursorPageResponse<WearLogTimelineItem>;

export async function listAllWearLogs(accessToken: string) {
  return fetchAllCursorPages((cursor) =>
    apiRequest<WearLogTimelineResponse>(buildApiPath("/wear-logs", { cursor, limit: 50 }), {
      headers: {
        Authorization: `Bearer ${accessToken}`
      },
      ttlSeconds: 10
    })
  );
}
