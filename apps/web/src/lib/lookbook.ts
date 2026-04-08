import { apiRequest, buildApiPath, fetchAllCursorPages, type CursorPageResponse } from "./api";

export type PrivateImage = {
  asset_id: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  url: string;
  expires_at: string;
};

export type LookbookSummary = {
  id: string;
  title: string;
  description: string | null;
  entry_count: number;
  cover_image: PrivateImage | null;
  created_at: string;
  updated_at: string;
};

export type LookbookOutfitReference = {
  id: string;
  title: string | null;
  is_favorite: boolean;
  is_archived: boolean;
  item_count: number;
  cover_image: PrivateImage | null;
};

export type LookbookEntry = {
  id: string;
  entry_type: "outfit" | "image" | "note";
  caption: string | null;
  note_text: string | null;
  sort_index: number;
  image: PrivateImage | null;
  outfit: LookbookOutfitReference | null;
  created_at: string;
  updated_at: string;
};

export type FlattenedLookbookEntry = {
  lookbook_id: string;
  lookbook_title: string;
  lookbook_description: string | null;
  lookbook_cover_image: PrivateImage | null;
  entry: LookbookEntry;
};

type LookbookListResponse = CursorPageResponse<LookbookSummary>;
type LookbookEntryListResponse = CursorPageResponse<LookbookEntry>;
type FlattenedLookbookEntryListResponse = CursorPageResponse<FlattenedLookbookEntry>;

function authHeaders(accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`
  };
}

export async function listAllLookbooks(accessToken: string) {
  return fetchAllCursorPages((cursor) =>
    apiRequest<LookbookListResponse>(buildApiPath("/lookbooks", { cursor, limit: 50 }), {
      headers: authHeaders(accessToken),
      ttlSeconds: 10
    })
  );
}

export async function listAllLookbookEntries(accessToken: string, lookbookId: string) {
  return fetchAllCursorPages((cursor) =>
    apiRequest<LookbookEntryListResponse>(
      buildApiPath(`/lookbooks/${lookbookId}/entries`, { cursor, limit: 50 }),
      {
        headers: authHeaders(accessToken),
        ttlSeconds: 10
      }
    )
  );
}

export async function listFlattenedLookbookEntries(accessToken: string) {
  return fetchAllCursorPages(
    (cursor) =>
      apiRequest<FlattenedLookbookEntryListResponse>(
        buildApiPath("/lookbooks/entries", { cursor, limit: 50 }),
        {
          headers: authHeaders(accessToken),
          ttlSeconds: 10
        }
      ),
    { maxPages: 20 }
  );
}

export async function listRecentLookbookEntries(accessToken: string, limit = 6) {
  const response = await apiRequest<FlattenedLookbookEntryListResponse>(
    buildApiPath("/lookbooks/entries", { limit }),
    {
      headers: authHeaders(accessToken),
      ttlSeconds: 10
    }
  );

  return response.items;
}

export async function getFlattenedLookbookEntry(accessToken: string, entryId: string) {
  return apiRequest<FlattenedLookbookEntry>(`/lookbooks/entries/${entryId}`, {
    headers: authHeaders(accessToken),
    ttlSeconds: 10
  });
}
