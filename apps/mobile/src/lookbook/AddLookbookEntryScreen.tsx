import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useFocusEffect, useLocalSearchParams, type Href } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View
} from "react-native";

import { useAuth } from "../auth/provider";
import { useClosetMetadataOptions, useConfirmedClosetBrowse } from "../closet/hooks";
import { selectSingleImage } from "../closet/upload";
import { formatDateTime, humanizeEnum } from "../lib/format";
import { createLookbookEntryWithSession, updateLookbookEntryWithSession, useLookbookEntryDetail } from "./hooks";
import { uploadLookbookAsset } from "./upload";
import { useWearLogDetail, useWearTimeline } from "../wear/hooks";
import { AppText } from "../ui";
import {
  EmptyPhotoState,
  FeatureSheet,
  FeatureTextArea,
  GlassIconButton,
  PrimaryActionButton,
  SecondaryActionButton
} from "../ui/feature-components";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";
import type {
  LookbookIntentValue,
  LookbookSelectedItem,
  LookbookSourceKindValue,
  LookbookStatusValue
} from "./types";
import { buildLookbookHeroUri, normalizeRole, toLookbookSelectedItem } from "./types";

const FALLBACK_OCCASIONS = ["everyday", "work", "formal", "travel"];
const FALLBACK_SEASONS = ["spring", "summer", "fall", "winter"];
const FALLBACK_STYLES = ["minimal", "classic", "polished", "casual"];

function sanitizeText(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function buildLinkedItemsPayload(items: LookbookSelectedItem[]) {
  return items.map((item, index) => ({
    closet_item_id: item.closet_item_id,
    role: item.role,
    sort_index: index
  }));
}

function tagOptions<T extends string>(values: T[]) {
  return values.length > 0 ? values : ([] as T[]);
}

export default function AddLookbookEntryScreen() {
  const params = useLocalSearchParams<{ entryId?: string; wearLogId?: string }>();
  const { session } = useAuth();
  const metadata = useClosetMetadataOptions(session?.access_token);
  const closet = useConfirmedClosetBrowse(session?.access_token, { include_archived: false }, 100);
  const detail = useLookbookEntryDetail(session?.access_token, params.entryId);
  const wearTimeline = useWearTimeline(session?.access_token, { status: "confirmed" }, 20);
  const [sourceKind, setSourceKind] = useState<LookbookSourceKindValue | null>(
    params.wearLogId ? "wear_log" : null
  );
  const [intent, setIntent] = useState<LookbookIntentValue>("inspiration");
  const [selectedWearLogId, setSelectedWearLogId] = useState<string | null>(params.wearLogId ?? null);
  const wearSource = useWearLogDetail(session?.access_token, selectedWearLogId);
  const [title, setTitle] = useState("");
  const [caption, setCaption] = useState("");
  const [notes, setNotes] = useState("");
  const [occasionTag, setOccasionTag] = useState<string | null>(null);
  const [seasonTag, setSeasonTag] = useState<string | null>(null);
  const [styleTag, setStyleTag] = useState<string | null>(null);
  const [primaryImageAssetId, setPrimaryImageAssetId] = useState<string | null>(null);
  const [coverPreviewUrl, setCoverPreviewUrl] = useState<string | null>(null);
  const [selectedItems, setSelectedItems] = useState<LookbookSelectedItem[]>([]);
  const [showClosetPicker, setShowClosetPicker] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [didHydrateEditState, setDidHydrateEditState] = useState(false);

  const isEditing = Boolean(params.entryId);
  const sourceLocked = isEditing || Boolean(params.wearLogId);
  const occasionOptions = metadata.data?.occasion_tags ?? FALLBACK_OCCASIONS;
  const seasonOptions = metadata.data?.season_tags ?? FALLBACK_SEASONS;
  const styleOptions = metadata.data?.style_tags ?? FALLBACK_STYLES;
  const wearPreviewUri = buildLookbookHeroUri(null, wearSource.detail);
  const effectivePreviewUri =
    coverPreviewUrl ??
    detail.detail?.primary_image?.url ??
    wearPreviewUri ??
    null;
  const closetRefreshRef = useRef(closet.refresh);
  const detailRefreshRef = useRef(detail.refresh);
  const wearTimelineRefreshRef = useRef(wearTimeline.refresh);
  const wearSourceRefreshRef = useRef(wearSource.refresh);

  useEffect(() => {
    closetRefreshRef.current = closet.refresh;
  }, [closet.refresh]);

  useEffect(() => {
    detailRefreshRef.current = detail.refresh;
  }, [detail.refresh]);

  useEffect(() => {
    wearTimelineRefreshRef.current = wearTimeline.refresh;
  }, [wearTimeline.refresh]);

  useEffect(() => {
    wearSourceRefreshRef.current = wearSource.refresh;
  }, [wearSource.refresh]);

  useFocusEffect(
    useCallback(() => {
      void closetRefreshRef.current();
      void wearTimelineRefreshRef.current();
      if (params.entryId) {
        void detailRefreshRef.current();
      }
      if (selectedWearLogId) {
        void wearSourceRefreshRef.current();
      }
    }, [params.entryId, selectedWearLogId])
  );

  useEffect(() => {
    if (!detail.detail || didHydrateEditState) {
      return;
    }

    setSourceKind(detail.detail.source_kind);
    setIntent(detail.detail.intent);
    setSelectedWearLogId(
      detail.detail.source_wear_log_id ?? detail.detail.source_snapshot?.wear_log_id ?? null
    );
    setTitle(detail.detail.title ?? "");
    setCaption(detail.detail.caption ?? "");
    setNotes(detail.detail.notes ?? "");
    setOccasionTag(detail.detail.occasion_tag);
    setSeasonTag(detail.detail.season_tag);
    setStyleTag(detail.detail.style_tag);
    setPrimaryImageAssetId(detail.detail.primary_image?.asset_id ?? null);
    setCoverPreviewUrl(detail.detail.primary_image?.url ?? null);
    setSelectedItems(detail.detail.linked_items.map((item) => toLookbookSelectedItem(item)));
    setDidHydrateEditState(true);
  }, [detail.detail, didHydrateEditState]);

  const selectedItemIds = useMemo(
    () => new Set(selectedItems.map((item) => item.closet_item_id)),
    [selectedItems]
  );

  async function handlePickGalleryImage() {
    if (!session?.access_token) {
      setError("Sign in again to continue.");
      return;
    }
    if (isUploadingImage) {
      return;
    }

    try {
      const asset = await selectSingleImage("library");
      if (!asset) {
        return;
      }

      setError(null);
      setIsUploadingImage(true);
      const uploaded = await uploadLookbookAsset(session.access_token, asset);
      setPrimaryImageAssetId(uploaded.asset_id);
      setCoverPreviewUrl(uploaded.url);
      if (!sourceKind) {
        setSourceKind("gallery_photo");
      }
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "The image could not be uploaded.");
    } finally {
      setIsUploadingImage(false);
    }
  }

  async function handleSave(targetStatus: LookbookStatusValue) {
    if (isSubmitting || isUploadingImage) {
      return;
    }
    if (!session?.access_token) {
      setError("Sign in again to continue.");
      return;
    }

    if (!sourceKind) {
      setError("Choose whether this look comes from a gallery photo or a daily log.");
      return;
    }

    if (sourceKind === "gallery_photo" && !primaryImageAssetId) {
      setError("Add a gallery photo before saving this look.");
      return;
    }

    if (sourceKind === "wear_log" && !selectedWearLogId) {
      setError("Choose a confirmed daily log first.");
      return;
    }

    if (targetStatus === "published" && !sanitizeText(title)) {
      setError("A published look needs a title.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const sharedPayload = {
        title: sanitizeText(title),
        caption: sanitizeText(caption),
        notes: sanitizeText(notes),
        occasion_tag: occasionTag,
        season_tag: seasonTag,
        style_tag: styleTag
      };

      let response;
      if (isEditing && params.entryId) {
        const updatePayload = {
          ...sharedPayload,
          status: targetStatus,
          ...(primaryImageAssetId ? { primary_image_asset_id: primaryImageAssetId } : {}),
          ...(
            sourceKind === "gallery_photo" || selectedItems.length > 0
              ? { linked_items: buildLinkedItemsPayload(selectedItems) }
              : {}
          )
        };
        response = await updateLookbookEntryWithSession(session.access_token, params.entryId, updatePayload);
      } else if (sourceKind === "gallery_photo") {
        response = await createLookbookEntryWithSession(session.access_token, {
          ...sharedPayload,
          source_kind: "gallery_photo",
          intent: intent === "recreate" ? "recreate" : "inspiration",
          status: targetStatus,
          primary_image_asset_id: primaryImageAssetId!,
          linked_items: buildLinkedItemsPayload(selectedItems)
        });
      } else {
        response = await createLookbookEntryWithSession(session.access_token, {
          ...sharedPayload,
          source_kind: "wear_log",
          source_wear_log_id: selectedWearLogId!,
          intent: "logged",
          status: targetStatus
        });

        if (primaryImageAssetId && response.primary_image?.asset_id !== primaryImageAssetId) {
          response = await updateLookbookEntryWithSession(session.access_token, response.id, {
            primary_image_asset_id: primaryImageAssetId
          });
        }
      }

      router.replace(`/lookbook/${response.id}` as Href);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "This look could not be saved.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function toggleSelectedClosetItem(candidate: LookbookSelectedItem) {
    setSelectedItems((current) => {
      if (selectedItemIds.has(candidate.closet_item_id)) {
        return current.filter((item) => item.closet_item_id !== candidate.closet_item_id);
      }

      return current.concat(candidate);
    });
  }

  if (isEditing && detail.isLoading && !didHydrateEditState) {
    return (
      <View style={styles.loadingScreen}>
        <AppText style={styles.loadingTitle}>Loading look</AppText>
        <AppText style={styles.loadingBody}>Pulling the saved photo, metadata, and linked items into the editor.</AppText>
      </View>
    );
  }

  if (isEditing && !detail.detail && detail.error) {
    return (
      <View style={styles.loadingScreen}>
        <AppText style={styles.loadingTitle}>Look unavailable</AppText>
        <AppText style={styles.loadingBody}>{detail.error}</AppText>
        <SecondaryActionButton
          label="Back"
          onPress={() => router.back()}
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={16} />}
        />
      </View>
    );
  }

  return (
    <>
      <ScrollView
        bounces={false}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        style={styles.screen}
      >
        <View style={styles.header}>
          <GlassIconButton
            icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
            onPress={() => router.back()}
          />
          <View style={styles.headerCopy}>
            <AppText style={styles.headerTitle}>
              {isEditing ? "Edit Look" : sourceKind === "wear_log" ? "Save Daily Look" : "New Look"}
            </AppText>
            <AppText style={styles.headerSubtitle}>
              {isEditing ? "Update the photo, tags, and linked closet items." : "Build a private look you can come back to later."}
            </AppText>
          </View>
        </View>

        {error ? (
          <View style={styles.noticeCard}>
            <AppText style={styles.noticeTitle}>Save blocked</AppText>
            <AppText style={styles.noticeBody}>{error}</AppText>
          </View>
        ) : null}

        {!sourceLocked && !sourceKind ? (
          <View style={styles.section}>
            <AppText style={styles.sectionLabel}>Choose a source</AppText>
            <View style={styles.sourceCards}>
              <Pressable
                onPress={() => setSourceKind("gallery_photo")}
                style={({ pressed }) => [styles.sourceCard, featureShadows.sm, pressed ? styles.pressedWide : null]}
              >
                <Feather color={featurePalette.foreground} name="image" size={22} />
                <AppText style={styles.sourceCardTitle}>Gallery</AppText>
                <AppText style={styles.sourceCardBody}>Use an inspiration photo or an older look you want to recreate.</AppText>
              </Pressable>
              <Pressable
                onPress={() => {
                  setSourceKind("wear_log");
                  setIntent("logged");
                }}
                style={({ pressed }) => [styles.sourceCard, featureShadows.sm, pressed ? styles.pressedWide : null]}
              >
                <Feather color={featurePalette.foreground} name="calendar" size={22} />
                <AppText style={styles.sourceCardTitle}>Daily Log</AppText>
                <AppText style={styles.sourceCardBody}>Save one confirmed wear log into the lookbook with its own title and tags.</AppText>
              </Pressable>
            </View>
          </View>
        ) : null}

        {sourceKind === "gallery_photo" ? (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <AppText style={styles.sectionLabel}>Cover image</AppText>
              {!sourceLocked ? (
                <Pressable onPress={() => setSourceKind(null)}>
                  <AppText style={styles.inlineLink}>Change source</AppText>
                </Pressable>
              ) : null}
            </View>

            {effectivePreviewUri ? (
              <Pressable onPress={() => void handlePickGalleryImage()} style={styles.photoFrame}>
                <Image contentFit="cover" source={{ uri: effectivePreviewUri }} style={styles.photoImage} />
                <View style={styles.photoOverlay}>
                  <AppText style={styles.photoOverlayLabel}>
                    {isUploadingImage ? "Uploading..." : "Replace photo"}
                  </AppText>
                </View>
              </Pressable>
            ) : (
              <EmptyPhotoState
                label={isUploadingImage ? "Uploading..." : "Pick from gallery"}
                onPress={() => void handlePickGalleryImage()}
                subtitle="One photo powers the grid and the detail page."
              />
            )}

            <View style={styles.chipRow}>
              {(["inspiration", "recreate"] as LookbookIntentValue[]).map((value) => (
                <Pressable
                  key={value}
                  onPress={() => setIntent(value)}
                  style={[
                    styles.choiceChip,
                    intent === value ? styles.choiceChipActive : null
                  ]}
                >
                  <AppText style={[styles.choiceChipLabel, intent === value ? styles.choiceChipLabelActive : null]}>
                    {humanizeEnum(value)}
                  </AppText>
                </Pressable>
              ))}
            </View>
          </View>
        ) : null}

        {sourceKind === "wear_log" ? (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <AppText style={styles.sectionLabel}>Daily log source</AppText>
              {!sourceLocked ? (
                <Pressable
                  onPress={() => {
                    setSelectedWearLogId(null);
                    setSourceKind(null);
                  }}
                >
                  <AppText style={styles.inlineLink}>Change source</AppText>
                </Pressable>
              ) : null}
            </View>

            {selectedWearLogId && wearSource.detail ? (
              <View style={[styles.sourcePreviewCard, featureShadows.sm]}>
                <View style={styles.sourcePreviewImageFrame}>
                  {wearPreviewUri ? (
                    <Image contentFit="cover" source={{ uri: wearPreviewUri }} style={styles.sourcePreviewImage} />
                  ) : (
                    <View style={styles.sourcePreviewFallback}>
                      <Feather color={featurePalette.muted} name="image" size={18} />
                    </View>
                  )}
                </View>
                <View style={styles.sourcePreviewCopy}>
                  <AppText style={styles.sourcePreviewTitle}>
                    {wearSource.detail.context ? humanizeEnum(wearSource.detail.context) : "Confirmed daily look"}
                  </AppText>
                  <AppText style={styles.sourcePreviewMeta}>
                    {formatDateTime(wearSource.detail.worn_at)} · {wearSource.detail.item_count} items
                  </AppText>
                </View>
                {!sourceLocked ? (
                  <Pressable onPress={() => setSelectedWearLogId(null)} style={styles.resetButton}>
                    <Feather color={featurePalette.foreground} name="refresh-cw" size={14} />
                  </Pressable>
                ) : null}
              </View>
            ) : selectedWearLogId && wearSource.error ? (
              <View style={styles.noticeCard}>
                <AppText style={styles.noticeTitle}>Daily log unavailable</AppText>
                <AppText style={styles.noticeBody}>{wearSource.error}</AppText>
                <View style={styles.noticeAction}>
                  <SecondaryActionButton
                    label="Choose another log"
                    onPress={() => setSelectedWearLogId(null)}
                    icon={<Feather color={featurePalette.foreground} name="refresh-cw" size={16} />}
                  />
                </View>
              </View>
            ) : wearTimeline.isLoading ? (
              <View style={styles.noticeCard}>
                <AppText style={styles.noticeBody}>Loading confirmed daily logs...</AppText>
              </View>
            ) : wearTimeline.items.length === 0 ? (
              <View style={styles.noticeCard}>
                <AppText style={styles.noticeTitle}>No confirmed daily logs yet</AppText>
                <AppText style={styles.noticeBody}>
                  Confirm at least one daily log before saving it into the lookbook.
                </AppText>
              </View>
            ) : (
              <View style={styles.pickList}>
                {wearTimeline.items.map((item) => (
                  <Pressable
                    key={item.id}
                    onPress={() => setSelectedWearLogId(item.id)}
                    style={({ pressed }) => [styles.pickCard, featureShadows.sm, pressed ? styles.pressedWide : null]}
                  >
                    <View style={styles.pickCardImageFrame}>
                      {item.cover_image?.url ? (
                        <Image contentFit="cover" source={{ uri: item.cover_image.url }} style={styles.pickCardImage} />
                      ) : (
                        <View style={styles.pickCardFallback}>
                          <Feather color={featurePalette.muted} name="camera" size={18} />
                        </View>
                      )}
                    </View>
                    <View style={styles.pickCardCopy}>
                      <AppText style={styles.pickCardTitle}>
                        {item.context ? humanizeEnum(item.context) : "Confirmed daily look"}
                      </AppText>
                      <AppText style={styles.pickCardMeta}>
                        {formatDateTime(item.worn_at)} · {item.item_count} items
                      </AppText>
                    </View>
                  </Pressable>
                ))}
              </View>
            )}

            {selectedWearLogId ? (
              <SecondaryActionButton
                label={isUploadingImage ? "Uploading..." : "Replace cover image"}
                onPress={() => void handlePickGalleryImage()}
                icon={<Feather color={featurePalette.foreground} name="image" size={16} />}
              />
            ) : null}
          </View>
        ) : null}

        {sourceKind ? (
          <>
            <View style={styles.section}>
              <AppText style={styles.sectionLabel}>Title</AppText>
              <TextInput
                onChangeText={setTitle}
                placeholder="Give this look a name"
                placeholderTextColor={featurePalette.muted}
                style={styles.input}
                value={title}
              />
            </View>

            <View style={styles.section}>
              <AppText style={styles.sectionLabel}>Caption</AppText>
              <TextInput
                onChangeText={setCaption}
                placeholder="Short note for the grid card"
                placeholderTextColor={featurePalette.muted}
                style={styles.input}
                value={caption}
              />
            </View>

            <View style={styles.section}>
              <AppText style={styles.sectionLabel}>Notes</AppText>
              <FeatureTextArea
                onChangeText={setNotes}
                placeholder="Add the details you want to remember."
                value={notes}
              />
            </View>

            <TagPicker
              label="Occasion"
              options={tagOptions(occasionOptions)}
              selectedValue={occasionTag}
              onSelect={setOccasionTag}
            />
            <TagPicker
              label="Season"
              options={tagOptions(seasonOptions)}
              selectedValue={seasonTag}
              onSelect={setSeasonTag}
            />
            <TagPicker
              label="Style"
              options={tagOptions(styleOptions)}
              selectedValue={styleTag}
              onSelect={setStyleTag}
            />

            {sourceKind === "gallery_photo" || isEditing ? (
              <View style={styles.section}>
                <View style={styles.sectionHeader}>
                  <AppText style={styles.sectionLabel}>Linked closet items</AppText>
                  <Pressable onPress={() => setShowClosetPicker(true)}>
                    <AppText style={styles.inlineLink}>
                      {selectedItems.length > 0 ? "Edit items" : "Link items"}
                    </AppText>
                  </Pressable>
                </View>
                {selectedItems.length > 0 ? (
                  <View style={styles.selectedItemList}>
                    {selectedItems.map((item) => (
                      <View key={item.closet_item_id} style={[styles.selectedItemCard, featureShadows.sm]}>
                        <View style={styles.selectedItemImageFrame}>
                          {item.image_url ? (
                            <Image contentFit="cover" source={{ uri: item.image_url }} style={styles.selectedItemImage} />
                          ) : (
                            <View style={styles.selectedItemFallback}>
                              <Feather color={featurePalette.muted} name="image" size={16} />
                            </View>
                          )}
                        </View>
                        <View style={styles.selectedItemCopy}>
                          <AppText numberOfLines={1} style={styles.selectedItemTitle}>
                            {item.title ?? "Closet item"}
                          </AppText>
                          <AppText style={styles.selectedItemMeta}>
                            {[item.primary_color, humanizeEnum(item.subcategory ?? item.category ?? item.role ?? "item")]
                              .filter(Boolean)
                              .join(" · ")}
                          </AppText>
                        </View>
                        <Pressable
                          onPress={() =>
                            setSelectedItems((current) =>
                              current.filter((candidate) => candidate.closet_item_id !== item.closet_item_id)
                            )
                          }
                          style={styles.removeButton}
                        >
                          <Feather color={featurePalette.danger} name="x" size={14} />
                        </Pressable>
                      </View>
                    ))}
                  </View>
                ) : (
                  <View style={styles.noticeCard}>
                    <AppText style={styles.noticeTitle}>No closet items linked</AppText>
                    <AppText style={styles.noticeBody}>
                      {sourceKind === "gallery_photo"
                        ? "Linking closet items is optional for gallery looks, but it makes the wear loop stronger."
                        : "This edit screen can override the linked items from the original daily log if you need to refine the look."}
                    </AppText>
                  </View>
                )}
              </View>
            ) : (
              <View style={styles.section}>
                <AppText style={styles.sectionLabel}>Closet linkage</AppText>
                <View style={styles.noticeCard}>
                  <AppText style={styles.noticeBody}>
                    The linked closet items will come from the confirmed daily log after this look is saved.
                  </AppText>
                </View>
              </View>
            )}

            <View style={styles.footerButtons}>
              <SecondaryActionButton
                label={isSubmitting ? "Saving..." : "Save Draft"}
                disabled={isSubmitting || isUploadingImage}
                onPress={() => void handleSave("draft")}
                icon={<Feather color={featurePalette.foreground} name="bookmark" size={16} />}
              />
              <PrimaryActionButton
                disabled={isSubmitting || isUploadingImage}
                label={isSubmitting ? "Publishing..." : "Publish"}
                onPress={() => void handleSave("published")}
                icon={<Feather color="#FFFFFF" name="check" size={16} />}
              />
            </View>
          </>
        ) : null}
      </ScrollView>

      <FeatureSheet
        title="Link Closet Items"
        visible={showClosetPicker}
        onClose={() => setShowClosetPicker(false)}
        footer={
          <PrimaryActionButton
            label="Done"
            onPress={() => setShowClosetPicker(false)}
            icon={<Feather color="#FFFFFF" name="check" size={16} />}
          />
        }
      >
        <View style={styles.pickList}>
          {closet.items.map((item) => {
            const candidate = toLookbookSelectedItem(item);
            const selected = selectedItemIds.has(candidate.closet_item_id);
            return (
              <Pressable
                key={candidate.closet_item_id}
                onPress={() => toggleSelectedClosetItem({ ...candidate, role: normalizeRole(candidate.category) })}
                style={({ pressed }) => [
                  styles.pickCard,
                  selected ? styles.pickCardSelected : null,
                  featureShadows.sm,
                  pressed ? styles.pressedWide : null
                ]}
              >
                <View style={styles.pickCardImageFrame}>
                  {candidate.image_url ? (
                    <Image contentFit="cover" source={{ uri: candidate.image_url }} style={styles.pickCardImage} />
                  ) : (
                    <View style={styles.pickCardFallback}>
                      <Feather color={featurePalette.muted} name="image" size={18} />
                    </View>
                  )}
                </View>
                <View style={styles.pickCardCopy}>
                  <AppText style={styles.pickCardTitle}>{candidate.title ?? "Closet item"}</AppText>
                  <AppText style={styles.pickCardMeta}>
                    {[candidate.primary_color, humanizeEnum(candidate.subcategory ?? candidate.category ?? "item")]
                      .filter(Boolean)
                      .join(" · ")}
                  </AppText>
                </View>
                {selected ? <Feather color={featurePalette.foreground} name="check" size={16} /> : null}
              </Pressable>
            );
          })}
        </View>
      </FeatureSheet>
    </>
  );
}

function TagPicker({
  label,
  options,
  selectedValue,
  onSelect
}: {
  label: string;
  options: string[];
  selectedValue: string | null;
  onSelect: (value: string | null) => void;
}) {
  return (
    <View style={styles.section}>
      <AppText style={styles.sectionLabel}>{label}</AppText>
      <View style={styles.chipWrap}>
        {options.map((value) => {
          const selected = selectedValue === value;
          return (
            <Pressable
              key={value}
              onPress={() => onSelect(selected ? null : value)}
              style={[styles.choiceChip, selected ? styles.choiceChipActive : null]}
            >
              <AppText style={[styles.choiceChipLabel, selected ? styles.choiceChipLabelActive : null]}>
                {humanizeEnum(value)}
              </AppText>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  content: {
    paddingTop: 56,
    paddingHorizontal: 20,
    paddingBottom: 40,
    gap: 20
  },
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 16
  },
  headerCopy: {
    flex: 1,
    paddingTop: 4
  },
  headerTitle: {
    ...featureTypography.title
  },
  headerSubtitle: {
    ...featureTypography.label,
    marginTop: 4
  },
  section: {
    gap: 12
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  sectionLabel: {
    ...featureTypography.microUpper
  },
  inlineLink: {
    fontFamily: "Manrope_700Bold",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  noticeCard: {
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    padding: 16,
    ...featureShadows.sm
  },
  noticeTitle: {
    ...featureTypography.bodyStrong,
    color: featurePalette.foreground
  },
  noticeBody: {
    ...featureTypography.label,
    marginTop: 4
  },
  noticeAction: {
    marginTop: 12
  },
  sourceCards: {
    gap: 12
  },
  sourceCard: {
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    padding: 20,
    gap: 10
  },
  sourceCardTitle: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 22,
    lineHeight: 28,
    color: featurePalette.foreground
  },
  sourceCardBody: {
    ...featureTypography.body
  },
  photoFrame: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: 24,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  photoImage: {
    width: "100%",
    height: "100%"
  },
  photoOverlay: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 12,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.86)",
    paddingVertical: 10,
    alignItems: "center"
  },
  photoOverlayLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 13,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  chipRow: {
    flexDirection: "row",
    gap: 8
  },
  chipWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  choiceChip: {
    borderRadius: 999,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 14,
    paddingVertical: 10
  },
  choiceChipActive: {
    backgroundColor: featurePalette.foreground
  },
  choiceChipLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 13,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  choiceChipLabelActive: {
    color: "#FFFFFF"
  },
  input: {
    height: 52,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    fontFamily: "Manrope_500Medium",
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground,
    ...featureShadows.sm
  },
  sourcePreviewCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 12
  },
  sourcePreviewImageFrame: {
    width: 72,
    height: 96,
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  sourcePreviewImage: {
    width: "100%",
    height: "100%"
  },
  sourcePreviewFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  sourcePreviewCopy: {
    flex: 1
  },
  sourcePreviewTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  sourcePreviewMeta: {
    ...featureTypography.label,
    marginTop: 4
  },
  resetButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: featurePalette.secondary
  },
  pickList: {
    gap: 10
  },
  pickCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 12
  },
  pickCardSelected: {
    backgroundColor: "#F1F5F9"
  },
  pickCardImageFrame: {
    width: 56,
    height: 72,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  pickCardImage: {
    width: "100%",
    height: "100%"
  },
  pickCardFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  pickCardCopy: {
    flex: 1
  },
  pickCardTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  pickCardMeta: {
    ...featureTypography.label,
    marginTop: 4
  },
  selectedItemList: {
    gap: 10
  },
  selectedItemCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 12
  },
  selectedItemImageFrame: {
    width: 56,
    height: 72,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  selectedItemImage: {
    width: "100%",
    height: "100%"
  },
  selectedItemFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  selectedItemCopy: {
    flex: 1
  },
  selectedItemTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  selectedItemMeta: {
    ...featureTypography.label,
    marginTop: 4
  },
  removeButton: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FEE2E2"
  },
  footerButtons: {
    gap: 12,
    paddingTop: 8
  },
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
    backgroundColor: featurePalette.background,
    gap: 10
  },
  loadingTitle: {
    ...featureTypography.title,
    textAlign: "center"
  },
  loadingBody: {
    ...featureTypography.body,
    textAlign: "center"
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
