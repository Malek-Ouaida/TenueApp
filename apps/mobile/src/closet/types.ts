export type ClosetMetadataCategoryOption = {
  name: string;
  subcategories: string[];
};

export type ClosetMetadataOptionsResponse = {
  taxonomy_version: string;
  required_confirmation_fields: string[];
  lifecycle_statuses: string[];
  processing_statuses: string[];
  review_statuses: string[];
  categories: ClosetMetadataCategoryOption[];
  colors: string[];
  materials: string[];
  patterns: string[];
  style_tags: string[];
  fit_tags: string[];
  occasion_tags: string[];
  season_tags: string[];
  silhouettes: string[];
  attributes: string[];
};

export type ClosetProcessingImageSnapshot = {
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

export type ClosetDraftSnapshot = {
  id: string;
  title: string | null;
  lifecycle_status: string;
  processing_status: string;
  review_status: string;
  failure_summary: string | null;
  has_primary_image: boolean;
  original_images: ClosetProcessingImageSnapshot[];
  created_at: string;
  updated_at: string;
};

export type ClosetUploadIntentRequest = {
  filename: string;
  mime_type: string;
  file_size: number;
  sha256: string;
};

export type PresignedUploadDescriptor = {
  method: string;
  url: string;
  headers: Record<string, string>;
};

export type ClosetUploadIntentResponse = {
  upload_intent_id: string;
  expires_at: string;
  upload: PresignedUploadDescriptor;
};

export type ClosetReviewListResponse = {
  items: ClosetDraftSnapshot[];
  next_cursor: string | null;
};

export type ClosetProcessingRunSnapshot = {
  id: string;
  run_type: string;
  status: string;
  retry_count: number;
  started_at: string | null;
  completed_at: string | null;
  failure_code: string | null;
};

export type ClosetProviderResultSnapshot = {
  id: string;
  provider_name: string;
  provider_model: string | null;
  provider_version: string | null;
  task_type: string;
  status: string;
  raw_payload: unknown;
  created_at: string;
};

export type ClosetProcessingSnapshot = {
  item_id: string;
  lifecycle_status: string;
  processing_status: string;
  review_status: string;
  failure_summary: string | null;
  can_reprocess: boolean;
  latest_run: ClosetProcessingRunSnapshot | null;
  provider_results: ClosetProviderResultSnapshot[];
  display_image: ClosetProcessingImageSnapshot | null;
  original_image: ClosetProcessingImageSnapshot | null;
  original_images: ClosetProcessingImageSnapshot[];
  thumbnail_image: ClosetProcessingImageSnapshot | null;
};

export type ClosetFieldCandidateSnapshot = {
  id: string;
  field_name: string;
  raw_value: unknown;
  normalized_candidate: unknown;
  confidence: number | null;
  applicability_state: string;
  conflict_notes: string | null;
  provider_result_id: string | null;
  created_at: string;
};

export type ClosetExtractionCurrentCandidateSet = {
  provider_result_id: string;
  status: string;
  created_at: string;
  field_candidates: ClosetFieldCandidateSnapshot[];
};

export type ClosetFieldCanonicalValue = string | string[] | null;

export type ClosetFieldStateSnapshot = {
  field_name: string;
  canonical_value: ClosetFieldCanonicalValue;
  source: string;
  confidence: number | null;
  review_state: string;
  applicability_state: string;
  taxonomy_version: string;
  updated_at: string;
};

export type ClosetMetadataProjectionSnapshot = {
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
  fit_tags: string[] | null;
  occasion_tags: string[] | null;
  season_tags: string[] | null;
  silhouette: string | null;
  attributes: string[] | null;
  confirmed_at: string | null;
  updated_at: string;
};

export type ClosetBrowseListItemSnapshot = {
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
  display_image: ClosetProcessingImageSnapshot | null;
  thumbnail_image: ClosetProcessingImageSnapshot | null;
};

export type ClosetBrowseListResponse = {
  items: ClosetBrowseListItemSnapshot[];
  next_cursor: string | null;
};

export type ClosetSimilaritySignalSnapshot = {
  code: string;
  label: string;
  contribution: number;
  metadata: Record<string, unknown> | null;
};

export type ClosetSimilarityEdgeSnapshot = {
  edge_id: string;
  item_a_id: string;
  item_b_id: string;
  label: string;
  similarity_type: string;
  decision_status: string;
  score: number;
  signals: ClosetSimilaritySignalSnapshot[];
};

export type ClosetSimilarityListItemSnapshot = {
  edge_id: string;
  label: string;
  similarity_type: string;
  decision_status: string;
  score: number;
  signals: ClosetSimilaritySignalSnapshot[];
  other_item: ClosetBrowseListItemSnapshot;
};

export type ClosetSimilarityListResponse = {
  item_id: string;
  similarity_status: string;
  latest_run: ClosetProcessingRunSnapshot | null;
  items: ClosetSimilarityListItemSnapshot[];
};

export type ClosetExtractionSnapshot = {
  item_id: string;
  lifecycle_status: string;
  review_status: string;
  extraction_status: string;
  normalization_status: string;
  field_states_stale: boolean;
  can_reextract: boolean;
  source_image: ClosetProcessingImageSnapshot | null;
  latest_run: ClosetProcessingRunSnapshot | null;
  latest_normalization_run: ClosetProcessingRunSnapshot | null;
  provider_results: ClosetProviderResultSnapshot[];
  current_candidate_set: ClosetExtractionCurrentCandidateSet | null;
  current_field_states: ClosetFieldStateSnapshot[];
  metadata_projection: ClosetMetadataProjectionSnapshot | null;
};

export type ClosetItemDetailSnapshot = {
  item_id: string;
  lifecycle_status: string;
  processing_status: string;
  review_status: string;
  failure_summary: string | null;
  confirmed_at: string;
  created_at: string;
  updated_at: string;
  display_image: ClosetProcessingImageSnapshot | null;
  thumbnail_image: ClosetProcessingImageSnapshot | null;
  original_image: ClosetProcessingImageSnapshot | null;
  original_images: ClosetProcessingImageSnapshot[];
  metadata_projection: ClosetMetadataProjectionSnapshot;
  field_states: ClosetFieldStateSnapshot[];
};

export type ClosetSuggestedFieldStateSnapshot = {
  canonical_value: ClosetFieldCanonicalValue;
  confidence: number | null;
  applicability_state: string;
  conflict_notes: string | null;
  provider_result_id: string | null;
  is_derived: boolean;
};

export type ClosetReviewFieldSnapshot = {
  field_name: string;
  required: boolean;
  blocking_confirmation: boolean;
  current_state: ClosetFieldStateSnapshot;
  suggested_state: ClosetSuggestedFieldStateSnapshot | null;
};

export type ClosetRetryActionSnapshot = {
  can_retry: boolean;
  default_step: ClosetRetryStep | null;
  reason: string | null;
};

export type ClosetItemReviewSnapshot = {
  item_id: string;
  lifecycle_status: string;
  processing_status: string;
  extraction_status: string;
  normalization_status: string;
  review_status: string;
  failure_summary: string | null;
  confirmed_at: string | null;
  review_version: string;
  can_confirm: boolean;
  missing_required_fields: string[];
  field_states_stale: boolean;
  retry_action: ClosetRetryActionSnapshot;
  latest_processing_run: ClosetProcessingRunSnapshot | null;
  latest_extraction_run: ClosetProcessingRunSnapshot | null;
  latest_normalization_run: ClosetProcessingRunSnapshot | null;
  display_image: ClosetProcessingImageSnapshot | null;
  original_image: ClosetProcessingImageSnapshot | null;
  original_images: ClosetProcessingImageSnapshot[];
  thumbnail_image: ClosetProcessingImageSnapshot | null;
  review_fields: ClosetReviewFieldSnapshot[];
  current_candidate_set: ClosetExtractionCurrentCandidateSet | null;
};

export type ClosetReviewFieldOperation =
  | "accept_suggestion"
  | "set_value"
  | "clear"
  | "mark_not_applicable";

export type ClosetReviewFieldChange = {
  field_name: string;
  operation: ClosetReviewFieldOperation;
  canonical_value?: ClosetFieldCanonicalValue;
};

export type ClosetReviewPatchRequest = {
  expected_review_version: string;
  changes: ClosetReviewFieldChange[];
};

export type ClosetConfirmRequest = {
  expected_review_version: string;
};

export type ClosetConfirmedItemFieldOperation =
  | "set_value"
  | "clear"
  | "mark_not_applicable";

export type ClosetConfirmedItemFieldChange = {
  field_name: string;
  operation: ClosetConfirmedItemFieldOperation;
  canonical_value?: ClosetFieldCanonicalValue;
};

export type ClosetConfirmedItemPatchRequest = {
  expected_item_version: string;
  changes: ClosetConfirmedItemFieldChange[];
};

export type ClosetConfirmedItemEditSnapshot = {
  item_id: string;
  lifecycle_status: string;
  processing_status: string;
  review_status: string;
  confirmed_at: string;
  updated_at: string;
  item_version: string;
  editable_fields: string[];
  display_image: ClosetProcessingImageSnapshot | null;
  thumbnail_image: ClosetProcessingImageSnapshot | null;
  original_image: ClosetProcessingImageSnapshot | null;
  original_images: ClosetProcessingImageSnapshot[];
  metadata_projection: ClosetMetadataProjectionSnapshot;
  field_states: ClosetFieldStateSnapshot[];
};

export type ClosetConfirmedItemImageReorderRequest = {
  image_ids: string[];
};

export type ClosetRetryStep =
  | "image_processing"
  | "metadata_extraction"
  | "normalization_projection";

export type ClosetRetryRequest = {
  step?: ClosetRetryStep | null;
};

export type ClosetHistoryEventSnapshot = {
  id: string;
  actor_user_id: string | null;
  actor_type: string;
  event_type: string;
  payload: unknown;
  created_at: string;
};

export type ClosetHistoryResponse = {
  items: ClosetHistoryEventSnapshot[];
  next_cursor: string | null;
};

export type ClosetBrowseFilters = {
  query?: string;
  category?: string;
  subcategory?: string;
  color?: string;
  material?: string;
  pattern?: string;
  include_archived?: boolean;
};

export type ClosetQueueSectionKey = "needs_review" | "processing" | "needs_attention";

export type ClosetQueueSection = {
  key: ClosetQueueSectionKey;
  title: string;
  items: ClosetDraftSnapshot[];
};
