import type {
  ClosetProcessingImageSnapshot,
  PresignedUploadDescriptor
} from "../closet/types";

export type WearContextValue =
  | "casual"
  | "work"
  | "event"
  | "travel"
  | "gym"
  | "lounge";

export type WearItemRoleValue =
  | "top"
  | "bottom"
  | "dress"
  | "outerwear"
  | "shoes"
  | "bag"
  | "accessory"
  | "other";

export type WearLogStatusValue =
  | "draft"
  | "processing"
  | "needs_review"
  | "confirmed"
  | "failed";

export type WearDetectedItemStatusValue = "detected" | "excluded" | "confirmed";
export type WearItemSourceValue = "manual" | "from_outfit" | "ai_matched" | "manual_override";

export type WearLogItemWriteRequest = {
  closet_item_id: string;
  role?: WearItemRoleValue | null;
  sort_index?: number | null;
  detected_item_id?: string | null;
  source?: WearItemSourceValue | null;
  match_confidence?: number | null;
};

export type ManualWearLogCreateRequest = {
  mode: "manual_items";
  wear_date: string;
  worn_at?: string | null;
  captured_at?: string | null;
  timezone_name?: string | null;
  context?: WearContextValue | null;
  vibe?: string | null;
  notes?: string | null;
  items: WearLogItemWriteRequest[];
};

export type PhotoUploadWearLogCreateRequest = {
  mode: "photo_upload";
  wear_date: string;
  worn_at?: string | null;
  captured_at?: string | null;
  timezone_name?: string | null;
  context?: WearContextValue | null;
  vibe?: string | null;
  notes?: string | null;
};

export type WearLogCreateRequest =
  | ManualWearLogCreateRequest
  | PhotoUploadWearLogCreateRequest;

export type WearLogUpdateRequest = {
  wear_date?: string | null;
  worn_at?: string | null;
  captured_at?: string | null;
  timezone_name?: string | null;
  context?: WearContextValue | null;
  vibe?: string | null;
  notes?: string | null;
  items?: WearLogItemWriteRequest[] | null;
};

export type WearUploadIntentRequest = {
  filename: string;
  mime_type: string;
  file_size: number;
  sha256: string;
};

export type WearUploadIntentResponse = {
  upload_intent_id: string;
  expires_at: string;
  upload: PresignedUploadDescriptor;
};

export type WearDetectedItemResolutionRequest = {
  detected_item_id: string;
  status: "excluded";
  exclusion_reason?: string | null;
};

export type WearLogConfirmRequest = {
  expected_review_version: string;
  worn_at?: string | null;
  captured_at?: string | null;
  timezone_name?: string | null;
  context?: WearContextValue | null;
  vibe?: string | null;
  notes?: string | null;
  items: WearLogItemWriteRequest[];
  resolved_detected_items?: WearDetectedItemResolutionRequest[];
};

export type WearMediaSnapshot = {
  asset_id: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  url: string;
  expires_at: string;
  photo_id?: string | null;
  position?: number | null;
};

export type WearLinkedOutfitSnapshot = {
  id: string;
  title: string | null;
  is_favorite: boolean;
  is_archived: boolean;
};

export type WearLoggedItemSnapshot = {
  closet_item_id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  display_image: ClosetProcessingImageSnapshot | null;
  thumbnail_image: ClosetProcessingImageSnapshot | null;
  role: string | null;
  sort_index: number;
  detected_item_id?: string | null;
};

export type WearCandidateItemSnapshot = {
  closet_item_id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primary_color: string | null;
  display_image: ClosetProcessingImageSnapshot | null;
  thumbnail_image: ClosetProcessingImageSnapshot | null;
};

export type WearMatchCandidateSnapshot = {
  id: string;
  closet_item_id: string;
  rank: number;
  score: number;
  signals: unknown;
  item: WearCandidateItemSnapshot | null;
};

export type WearDetectedItemSnapshot = {
  id: string;
  predicted_role: string | null;
  predicted_category: string | null;
  predicted_subcategory: string | null;
  predicted_colors: string[];
  confidence: number | null;
  bbox: Record<string, number> | null;
  status: WearDetectedItemStatusValue;
  exclusion_reason: string | null;
  crop_image: WearMediaSnapshot | null;
  candidate_matches: WearMatchCandidateSnapshot[];
};

export type WearLogDetailSnapshot = {
  id: string;
  wear_date: string;
  worn_at: string;
  worn_time_precision: string;
  captured_at: string | null;
  timezone_name: string | null;
  source: string;
  status: WearLogStatusValue;
  context: string | null;
  vibe: string | null;
  notes: string | null;
  is_confirmed: boolean;
  confirmed_at: string | null;
  archived_at: string | null;
  item_count: number;
  cover_image: WearMediaSnapshot | null;
  primary_photo: WearMediaSnapshot | null;
  photos: WearMediaSnapshot[];
  linked_outfit: WearLinkedOutfitSnapshot | null;
  items: WearLoggedItemSnapshot[];
  detected_items: WearDetectedItemSnapshot[];
  review_version: string;
  can_confirm: boolean;
  failure_code: string | null;
  failure_summary: string | null;
  created_at: string;
  updated_at: string;
};

export type WearLogTimelineItemSnapshot = {
  id: string;
  wear_date: string;
  worn_at: string;
  context: string | null;
  status: WearLogStatusValue;
  item_count: number;
  source: string;
  is_confirmed: boolean;
  cover_image: WearMediaSnapshot | null;
  outfit_title: string | null;
  created_at: string;
  updated_at: string;
};

export type WearLogTimelineResponse = {
  items: WearLogTimelineItemSnapshot[];
  next_cursor: string | null;
};

export type WearCalendarEventSnapshot = {
  id: string;
  worn_at: string;
  status: WearLogStatusValue;
  item_count: number;
  cover_image: WearMediaSnapshot | null;
  title: string | null;
  context: string | null;
};

export type WearCalendarDaySnapshot = {
  date: string;
  event_count: number;
  primary_event_id: string | null;
  primary_cover_image: WearMediaSnapshot | null;
  events: WearCalendarEventSnapshot[];
  has_wear_log: boolean;
  wear_log_id: string | null;
  item_count: number;
  source: string | null;
  is_confirmed: boolean | null;
  cover_image: WearMediaSnapshot | null;
  outfit_title: string | null;
};

export type WearCalendarResponse = {
  days: WearCalendarDaySnapshot[];
};
