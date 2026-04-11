import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../../../src/auth/provider";
import {
  getConfirmedClosetItemEdit,
  patchConfirmedClosetItem,
  removeConfirmedClosetItemImage,
  reorderConfirmedClosetItemImages,
  setConfirmedClosetItemPrimaryImage
} from "../../../../src/closet/client";
import { useClosetMetadataOptions } from "../../../../src/closet/hooks";
import {
  asString,
  asStringArray,
  fieldIsMultiValue,
  formatFieldValue,
  selectionOptionsForField
} from "../../../../src/closet/reviewDeckShared";
import { uploadConfirmedClosetItemImage, selectSingleImage } from "../../../../src/closet/upload";
import type {
  ClosetConfirmedItemEditSnapshot,
  ClosetFieldCanonicalValue,
  ClosetFieldStateSnapshot
} from "../../../../src/closet/types";
import { humanizeEnum } from "../../../../src/lib/format";
import {
  triggerErrorHaptic,
  triggerSelectionHaptic,
  triggerSuccessHaptic
} from "../../../../src/lib/haptics";
import { ApiError } from "../../../../src/lib/api";
import { colors, fontFamilies } from "../../../../src/theme";
import { AppText, Button, ModalSheet, Screen, SkeletonBlock, TextField } from "../../../../src/ui";

const palette = {
  background: "#FAF9F7",
  surface: "#FFFFFF",
  text: "#0F172A",
  muted: "#94A3B8",
  warmGray: "#64748B",
  border: "#E2E8F0",
  secondary: "#F8F8F6",
  shadow: "rgba(15, 23, 42, 0.08)",
  destructive: "#B05246",
  warning: "#C26A2E"
} as const;

type SelectionSheetState = {
  fieldName: string;
  multi: boolean;
  options: string[];
  required: boolean;
  selected: string[];
  title: string;
};

function formatStateValue(fieldState: ClosetFieldStateSnapshot | undefined) {
  if (!fieldState) {
    return "Not set";
  }

  if (fieldState.applicability_state === "not_applicable") {
    return "Not applicable";
  }

  if (fieldState.applicability_state === "unknown") {
    return "Unknown";
  }

  return formatFieldValue(fieldState.canonical_value) ?? "Not set";
}

function fieldLabel(fieldName: string) {
  switch (fieldName) {
    case "colors":
      return "Color";
    case "style_tags":
      return "Style";
    case "fit_tags":
      return "Fit";
    case "season_tags":
      return "Season";
    case "occasion_tags":
      return "Occasion";
    case "subcategory":
      return "Subcategory";
    default:
      return humanizeEnum(fieldName);
  }
}

function orderFieldStates(snapshot: ClosetConfirmedItemEditSnapshot | null) {
  if (!snapshot) {
    return [] as ClosetFieldStateSnapshot[];
  }

  return snapshot.editable_fields
    .map((fieldName) => snapshot.field_states.find((field) => field.field_name === fieldName))
    .filter((field): field is ClosetFieldStateSnapshot => Boolean(field));
}

export default function ConfirmedClosetItemEditScreen() {
  const params = useLocalSearchParams<{ itemId: string | string[] }>();
  const itemId = Array.isArray(params.itemId) ? params.itemId[0] : params.itemId;
  const { session } = useAuth();
  const metadata = useClosetMetadataOptions(session?.access_token);

  const [snapshot, setSnapshot] = useState<ClosetConfirmedItemEditSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [titleInput, setTitleInput] = useState("");
  const [brandInput, setBrandInput] = useState("");
  const [sheet, setSheet] = useState<SelectionSheetState | null>(null);

  const fieldStates = useMemo(() => orderFieldStates(snapshot), [snapshot]);
  const currentCategory = useMemo(
    () => asString(fieldStates.find((field) => field.field_name === "category")?.canonical_value ?? null),
    [fieldStates]
  );
  const categoryField = useMemo(
    () => fieldStates.find((field) => field.field_name === "category") ?? null,
    [fieldStates]
  );
  const editableMetadataFields = useMemo(
    () => fieldStates.filter((field) => !["title", "brand", "category"].includes(field.field_name)),
    [fieldStates]
  );

  const heroImage =
    snapshot?.display_image?.url ??
    snapshot?.thumbnail_image?.url ??
    snapshot?.original_image?.url ??
    snapshot?.original_images[0]?.url ??
    null;

  const load = useCallback(async () => {
    if (!session?.access_token || !itemId) {
      setSnapshot(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const nextSnapshot = await getConfirmedClosetItemEdit(session.access_token, itemId);
      setSnapshot(nextSnapshot);
      setTitleInput(
        asString(nextSnapshot.field_states.find((field) => field.field_name === "title")?.canonical_value ?? null) ??
          ""
      );
      setBrandInput(
        asString(nextSnapshot.field_states.find((field) => field.field_name === "brand")?.canonical_value ?? null) ??
          ""
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        router.replace(`/closet/${itemId}` as Href);
        return;
      }

      setNotice(error instanceof Error ? error.message : "Edit snapshot could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }, [itemId, session?.access_token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function applyChanges(
    changes: Array<{
      field_name: string;
      operation: "set_value" | "clear" | "mark_not_applicable";
      canonical_value?: ClosetFieldCanonicalValue;
    }>
  ) {
    if (!session?.access_token || !itemId || !snapshot) {
      return false;
    }

    setIsMutating(true);
    setNotice(null);

    try {
      const nextSnapshot = await patchConfirmedClosetItem(session.access_token, itemId, {
        expected_item_version: snapshot.item_version,
        changes
      });
      setSnapshot(nextSnapshot);
      await triggerSuccessHaptic();
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.code === "stale_review_version") {
        await load();
        setNotice("This item changed on the server, so Tenue refreshed the latest version.");
        await triggerSelectionHaptic();
        return false;
      }

      setNotice(error instanceof Error ? error.message : "Changes could not be saved.");
      await triggerErrorHaptic();
      return false;
    } finally {
      setIsMutating(false);
    }
  }

  async function saveTextField(fieldName: "title" | "brand", value: string) {
    const normalized = value.trim();
    await applyChanges(
      normalized
        ? [
            {
              field_name: fieldName,
              operation: "set_value",
              canonical_value: normalized
            }
          ]
        : [
            {
              field_name: fieldName,
              operation: "clear"
            }
          ]
    );
  }

  function openSelectionSheet(fieldName: string) {
    const fieldState = fieldStates.find((field) => field.field_name === fieldName);
    if (!fieldState) {
      return;
    }

    const multi = fieldIsMultiValue(fieldName);
    const selected = multi
      ? asStringArray(fieldState.canonical_value)
      : [asString(fieldState.canonical_value) ?? ""].filter(Boolean);

    setSheet({
      fieldName,
      multi,
      options: selectionOptionsForField(fieldName, metadata.data ?? null, currentCategory),
      required: ["category", "subcategory"].includes(fieldName),
      selected,
      title: fieldLabel(fieldName)
    });
  }

  async function applySheetSelection() {
    if (!sheet) {
      return;
    }

    const normalizedSelection = sheet.selected.filter(Boolean);
    const success = await applyChanges(
      normalizedSelection.length === 0
        ? [
            {
              field_name: sheet.fieldName,
              operation: "clear"
            }
          ]
        : [
            {
              field_name: sheet.fieldName,
              operation: "set_value",
              canonical_value: sheet.multi ? normalizedSelection : normalizedSelection[0]
            }
          ]
    );

    if (success) {
      setSheet(null);
    }
  }

  async function markSheetNotApplicable() {
    if (!sheet) {
      return;
    }

    const success = await applyChanges([
      {
        field_name: sheet.fieldName,
        operation: "mark_not_applicable"
      }
    ]);

    if (success) {
      setSheet(null);
    }
  }

  async function handleAddImage(source: "camera" | "library") {
    if (!session?.access_token || !itemId) {
      return;
    }

    try {
      const asset = await selectSingleImage(source);
      if (!asset) {
        return;
      }

      setIsUploading(true);
      setNotice("Uploading image…");
      await uploadConfirmedClosetItemImage({
        accessToken: session.access_token,
        asset,
        itemId
      });
      await load();
      setNotice("Image added. Tenue is refreshing processed imagery.");
      await triggerSuccessHaptic();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Image upload failed.");
      await triggerErrorHaptic();
    } finally {
      setIsUploading(false);
    }
  }

  async function moveImage(imageId: string, direction: -1 | 1) {
    if (!session?.access_token || !itemId || !snapshot) {
      return;
    }

    const imageIds = snapshot.original_images
      .map((image) => image.image_id)
      .filter((value): value is string => Boolean(value));
    const currentIndex = imageIds.indexOf(imageId);
    const nextIndex = currentIndex + direction;
    if (currentIndex < 0 || nextIndex < 0 || nextIndex >= imageIds.length) {
      return;
    }

    const nextImageIds = [...imageIds];
    [nextImageIds[currentIndex], nextImageIds[nextIndex]] = [nextImageIds[nextIndex], nextImageIds[currentIndex]];

    try {
      setIsMutating(true);
      await reorderConfirmedClosetItemImages(session.access_token, itemId, {
        image_ids: nextImageIds
      });
      await load();
      await triggerSelectionHaptic();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Image order could not be updated.");
      await triggerErrorHaptic();
    } finally {
      setIsMutating(false);
    }
  }

  async function setPrimaryImage(imageId: string) {
    if (!session?.access_token || !itemId) {
      return;
    }

    try {
      setIsMutating(true);
      await setConfirmedClosetItemPrimaryImage(session.access_token, itemId, imageId);
      await load();
      setNotice("Primary image updated. Tenue is refreshing processed imagery.");
      await triggerSuccessHaptic();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Primary image could not be updated.");
      await triggerErrorHaptic();
    } finally {
      setIsMutating(false);
    }
  }

  async function removeImage(imageId: string) {
    if (!session?.access_token || !itemId) {
      return;
    }

    try {
      setIsMutating(true);
      await removeConfirmedClosetItemImage(session.access_token, itemId, imageId);
      await load();
      await triggerSuccessHaptic();
    } catch (error) {
      if (error instanceof ApiError && error.code === "last_confirmed_item_image_required") {
        setNotice("Confirmed items must keep at least one original image.");
      } else {
        setNotice(error instanceof Error ? error.message : "Image could not be removed.");
      }
      await triggerErrorHaptic();
    } finally {
      setIsMutating(false);
    }
  }

  if (isLoading) {
    return (
      <View style={styles.loadingScreen}>
        <SkeletonBlock height={80} />
        <SkeletonBlock height={320} />
        <SkeletonBlock height={240} />
      </View>
    );
  }

  if (!snapshot) {
    return (
      <View style={styles.loadingScreen}>
        <AppText color={palette.muted} style={styles.emptyCopy}>
          Confirmed item editing could not be loaded.
        </AppText>
      </View>
    );
  }

  return (
    <>
      <Screen backgroundColor={palette.background} contentContainerStyle={styles.screenContent}>
        <View style={styles.header}>
          <Pressable
            onPress={() => router.back()}
            style={({ pressed }) => [styles.headerButton, pressed ? styles.pressed : null]}
          >
            <Feather color={palette.text} name="arrow-left" size={18} />
          </Pressable>
          <View style={styles.headerCopy}>
            <AppText color={palette.text} style={styles.headerTitle}>
              Edit Item
            </AppText>
            <AppText color={palette.muted} style={styles.headerSubtitle}>
              Confirmed metadata and media stay synced to the backend.
            </AppText>
          </View>
        </View>

        <View style={styles.heroCard}>
          {heroImage ? (
            <Image contentFit="cover" source={{ uri: heroImage }} style={styles.heroImage} />
          ) : (
            <View style={[styles.heroImage, styles.imageFallback]} />
          )}
          <View style={styles.heroCopy}>
            <AppText color={palette.text} style={styles.heroTitle}>
              {snapshot.metadata_projection.title ?? humanizeEnum(snapshot.metadata_projection.subcategory ?? "closet item")}
            </AppText>
            <AppText color={palette.warmGray} style={styles.heroMeta}>
              Version {snapshot.item_version.slice(0, 8)} · {humanizeEnum(snapshot.processing_status)}
            </AppText>
          </View>
        </View>

        {["pending", "running", "completed_with_issues"].includes(snapshot.processing_status) ? (
          <View style={styles.noticeCard}>
            <AppText color={palette.text} style={styles.noticeTitle}>
              Media refresh in progress
            </AppText>
            <AppText color={palette.warmGray} style={styles.noticeBody}>
              Tenue is updating processed imagery after the latest confirmed-item media change.
            </AppText>
          </View>
        ) : null}

        {notice ? (
          <View style={styles.noticeCard}>
            <AppText color={palette.text} style={styles.noticeTitle}>
              Update
            </AppText>
            <AppText color={palette.warmGray} style={styles.noticeBody}>
              {notice}
            </AppText>
          </View>
        ) : null}

        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <AppText color={palette.text} style={styles.sectionTitle}>
              Images
            </AppText>
            <View style={styles.sectionActions}>
              <Button
                label="Camera"
                onPress={() => void handleAddImage("camera")}
                size="sm"
                variant="secondary"
                disabled={isUploading || isMutating}
              />
              <Button
                label={isUploading ? "Uploading…" : "Library"}
                onPress={() => void handleAddImage("library")}
                size="sm"
                variant="secondary"
                disabled={isUploading || isMutating}
              />
            </View>
          </View>

          <View style={styles.mediaStack}>
            {snapshot.original_images.map((image, index) => {
              const imageId = image.image_id;

              return (
                <View key={image.asset_id} style={styles.mediaCard}>
                  <Image contentFit="cover" source={{ uri: image.url }} style={styles.mediaImage} />
                  <View style={styles.mediaCopy}>
                    <View style={styles.mediaMetaRow}>
                      <AppText color={palette.text} style={styles.mediaTitle}>
                        {image.is_primary ? "Primary image" : `Image ${index + 1}`}
                      </AppText>
                      <AppText color={palette.muted} style={styles.mediaCaption}>
                        Position {image.position ?? index}
                      </AppText>
                    </View>
                    <View style={styles.mediaActionRow}>
                      {!image.is_primary && imageId ? (
                        <ActionChip
                          label="Set primary"
                          onPress={() => void setPrimaryImage(imageId)}
                        />
                      ) : null}
                      {imageId && index > 0 ? (
                        <ActionChip
                          label="Move left"
                          onPress={() => void moveImage(imageId, -1)}
                        />
                      ) : null}
                      {imageId && index < snapshot.original_images.length - 1 ? (
                        <ActionChip
                          label="Move right"
                          onPress={() => void moveImage(imageId, 1)}
                        />
                      ) : null}
                      {imageId ? (
                        <ActionChip destructive label="Remove" onPress={() => void removeImage(imageId)} />
                      ) : null}
                    </View>
                  </View>
                </View>
              );
            })}
          </View>
        </View>

        <View style={styles.section}>
          <AppText color={palette.text} style={styles.sectionTitle}>
            Text fields
          </AppText>
          <View style={styles.formCard}>
            <TextField
              label="Title"
              placeholder="Closet item title"
              value={titleInput}
              onChangeText={setTitleInput}
            />
            <View style={styles.inlineActions}>
              <Button
                label="Save title"
                onPress={() => void saveTextField("title", titleInput)}
                size="sm"
                variant="secondary"
                disabled={isMutating}
              />
              <ActionChip
                label="Clear"
                onPress={() => void applyChanges([{ field_name: "title", operation: "clear" }])}
              />
            </View>

            <TextField
              label="Brand"
              placeholder="Brand"
              value={brandInput}
              onChangeText={setBrandInput}
            />
            <View style={styles.inlineActions}>
              <Button
                label="Save brand"
                onPress={() => void saveTextField("brand", brandInput)}
                size="sm"
                variant="secondary"
                disabled={isMutating}
              />
              <ActionChip
                label="Not applicable"
                onPress={() =>
                  void applyChanges([{ field_name: "brand", operation: "mark_not_applicable" }])
                }
              />
            </View>
          </View>
        </View>

        <View style={styles.section}>
          <AppText color={palette.text} style={styles.sectionTitle}>
            Metadata
          </AppText>
          <View style={styles.fieldsCard}>
            {categoryField ? (
              <View style={styles.readonlyFieldRow}>
                <AppText color={palette.muted} style={styles.fieldLabel}>
                  Category
                </AppText>
                <View style={styles.fieldValueRow}>
                  <AppText color={palette.text} numberOfLines={2} style={styles.fieldValue}>
                    {formatStateValue(categoryField)}
                  </AppText>
                </View>
                <AppText color={palette.warmGray} style={styles.readonlyFieldHelper}>
                  Change subcategory to move this item into another category.
                </AppText>
                {editableMetadataFields.length > 0 ? <View style={styles.divider} /> : null}
              </View>
            ) : null}

            {editableMetadataFields.map((field, index) => (
                <Pressable
                  key={field.field_name}
                  onPress={() => openSelectionSheet(field.field_name)}
                  style={({ pressed }) => [styles.fieldRow, pressed ? styles.pressed : null]}
                >
                  <AppText color={palette.muted} style={styles.fieldLabel}>
                    {fieldLabel(field.field_name)}
                  </AppText>
                  <View style={styles.fieldValueRow}>
                    <AppText color={palette.text} numberOfLines={2} style={styles.fieldValue}>
                      {formatStateValue(field)}
                    </AppText>
                    <Feather color={palette.muted} name="chevron-right" size={16} />
                  </View>
                  {index < editableMetadataFields.length - 1 ? (
                    <View style={styles.divider} />
                  ) : null}
                </Pressable>
              ))}
          </View>
        </View>
      </Screen>

      <ModalSheet
        footer={
          <View style={styles.sheetFooter}>
            {!sheet?.required ? (
              <Button
                label="Not applicable"
                onPress={() => void markSheetNotApplicable()}
                size="sm"
                variant="secondary"
                disabled={isMutating}
              />
            ) : null}
            <Button
              label="Save"
              onPress={() => void applySheetSelection()}
              size="sm"
              variant="secondary"
              disabled={isMutating || (sheet?.required && (sheet.selected.length ?? 0) === 0)}
            />
          </View>
        }
        onClose={() => setSheet(null)}
        visible={Boolean(sheet)}
      >
        <AppText color={palette.text} style={styles.sheetTitle}>
          {sheet?.title}
        </AppText>
        <View style={styles.sheetOptionGrid}>
          {sheet?.options.map((option) => {
            const selected = sheet.selected.includes(option);

            return (
              <Pressable
                key={option}
                onPress={() => {
                  if (!sheet) {
                    return;
                  }

                  setSheet((current) => {
                    if (!current) {
                      return current;
                    }

                    const nextSelected = current.multi
                      ? selected
                        ? current.selected.filter((value) => value !== option)
                        : current.selected.concat(option)
                      : [option];

                    return {
                      ...current,
                      selected: nextSelected
                    };
                  });
                }}
                style={({ pressed }) => [
                  styles.sheetOption,
                  selected ? styles.sheetOptionActive : null,
                  pressed ? styles.pressed : null
                ]}
              >
                <AppText color={selected ? colors.white : palette.text} style={styles.sheetOptionLabel}>
                  {humanizeEnum(option)}
                </AppText>
              </Pressable>
            );
          })}
        </View>
      </ModalSheet>
    </>
  );
}

function ActionChip({
  destructive = false,
  label,
  onPress
}: {
  destructive?: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.actionChip,
        destructive ? styles.actionChipDestructive : null,
        pressed ? styles.pressed : null
      ]}
    >
      <AppText color={destructive ? palette.destructive : palette.text} style={styles.actionChipLabel}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screenContent: {
    paddingBottom: 132
  },
  loadingScreen: {
    flex: 1,
    backgroundColor: palette.background,
    paddingHorizontal: 24,
    paddingTop: 24,
    gap: 20
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16
  },
  headerButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.9)",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 12,
    elevation: 4
  },
  headerCopy: {
    flex: 1
  },
  headerTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 20,
    lineHeight: 24
  },
  headerSubtitle: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  heroCard: {
    borderRadius: 24,
    backgroundColor: palette.surface,
    overflow: "hidden",
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 1,
    shadowRadius: 18,
    elevation: 5
  },
  heroImage: {
    width: "100%",
    aspectRatio: 4 / 5,
    backgroundColor: palette.secondary
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: palette.border
  },
  heroCopy: {
    padding: 18,
    gap: 4
  },
  heroTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 24,
    lineHeight: 28
  },
  heroMeta: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  noticeCard: {
    borderRadius: 18,
    backgroundColor: palette.surface,
    padding: 16,
    gap: 4
  },
  noticeTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  noticeBody: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 17
  },
  section: {
    gap: 12
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12
  },
  sectionTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 13,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase"
  },
  sectionActions: {
    flexDirection: "row",
    gap: 8
  },
  mediaStack: {
    gap: 12
  },
  mediaCard: {
    borderRadius: 18,
    backgroundColor: palette.surface,
    padding: 12,
    flexDirection: "row",
    gap: 12
  },
  mediaImage: {
    width: 76,
    height: 96,
    borderRadius: 14,
    backgroundColor: palette.secondary
  },
  mediaCopy: {
    flex: 1,
    gap: 10
  },
  mediaMetaRow: {
    gap: 2
  },
  mediaTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  mediaCaption: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  mediaActionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  formCard: {
    borderRadius: 20,
    backgroundColor: palette.surface,
    padding: 16,
    gap: 12
  },
  inlineActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  fieldsCard: {
    borderRadius: 20,
    backgroundColor: palette.surface,
    overflow: "hidden"
  },
  readonlyFieldRow: {
    paddingHorizontal: 18,
    paddingVertical: 15
  },
  fieldRow: {
    paddingHorizontal: 18,
    paddingVertical: 15
  },
  fieldLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18
  },
  fieldValueRow: {
    marginTop: 6,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12
  },
  fieldValue: {
    flex: 1,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  readonlyFieldHelper: {
    marginTop: 8,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 17
  },
  divider: {
    position: "absolute",
    left: 18,
    right: 18,
    bottom: 0,
    height: 1,
    backgroundColor: palette.border
  },
  actionChip: {
    borderRadius: 999,
    backgroundColor: palette.secondary,
    paddingHorizontal: 12,
    paddingVertical: 8
  },
  actionChipDestructive: {
    backgroundColor: "#FFF1F1"
  },
  actionChipLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16
  },
  sheetFooter: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: 8
  },
  sheetTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 22,
    lineHeight: 26
  },
  sheetOptionGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  sheetOption: {
    borderRadius: 999,
    backgroundColor: palette.secondary,
    paddingHorizontal: 12,
    paddingVertical: 10
  },
  sheetOptionActive: {
    backgroundColor: palette.text
  },
  sheetOptionLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16
  },
  emptyCopy: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    textAlign: "center"
  },
  pressed: {
    opacity: 0.78
  }
});
