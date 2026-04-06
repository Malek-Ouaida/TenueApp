import { Image } from "expo-image";
import * as Haptics from "expo-haptics";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useClosetMetadataOptions, useClosetReviewItem } from "../../../src/closet/hooks";
import {
  buildReviewFieldHelper,
  CLOSET_FIELD_ORDER,
  formatFieldValue,
  getReviewFieldStateLabel,
  getReviewFieldStateTone,
  getReviewItemPreview,
  getReviewRail,
  getRetryStepLabel,
  getStatusChipTone,
  humanizeStatus
} from "../../../src/closet/status";
import type {
  ClosetFieldCanonicalValue,
  ClosetMetadataCategoryOption,
  ClosetReviewFieldChange,
  ClosetReviewFieldSnapshot
} from "../../../src/closet/types";
import { colors, radius, spacing } from "../../../src/theme";
import {
  AppText,
  BrandMark,
  Button,
  Card,
  Chip,
  ModalSheet,
  Screen,
  SkeletonBlock,
  TextField
} from "../../../src/ui";

type SelectionSheetState = {
  fieldName: string;
  multi: boolean;
  options: string[];
  selected: string[];
  title: string;
};

function asString(value: ClosetFieldCanonicalValue): string | null {
  return typeof value === "string" ? value : null;
}

function asStringArray(value: ClosetFieldCanonicalValue): string[] {
  return Array.isArray(value) ? value : [];
}

function currentValueLabel(field: ClosetReviewFieldSnapshot) {
  if (field.current_state.applicability_state === "not_applicable") {
    return "Not applicable";
  }

  if (field.current_state.applicability_state === "unknown") {
    return "Unknown";
  }

  return formatFieldValue(field.current_state.canonical_value) ?? "Unknown";
}

function selectionOptionsForField(
  fieldName: string,
  categories: ClosetMetadataCategoryOption[],
  metadata: ReturnType<typeof useClosetMetadataOptions>["data"],
  currentCategory: string | null
) {
  if (!metadata) {
    return [];
  }

  switch (fieldName) {
    case "category":
      return categories.map((entry) => entry.name);
    case "subcategory": {
      if (currentCategory) {
        return categories.find((entry) => entry.name === currentCategory)?.subcategories ?? [];
      }
      return categories.flatMap((entry) => entry.subcategories);
    }
    case "colors":
      return metadata.colors;
    case "material":
      return metadata.materials;
    case "pattern":
      return metadata.patterns;
    case "style_tags":
      return metadata.style_tags;
    case "occasion_tags":
      return metadata.occasion_tags;
    case "season_tags":
      return metadata.season_tags;
    default:
      return [];
  }
}

export default function ReviewItemScreen() {
  const params = useLocalSearchParams<{ itemId: string | string[] }>();
  const itemId = Array.isArray(params.itemId) ? params.itemId[0] : params.itemId;
  const { session } = useAuth();
  const metadata = useClosetMetadataOptions(session?.access_token);
  const reviewFlow = useClosetReviewItem(session?.access_token, itemId);
  const [sheet, setSheet] = useState<SelectionSheetState | null>(null);
  const [titleInput, setTitleInput] = useState("");
  const [brandInput, setBrandInput] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const review = reviewFlow.review;
  const categories = metadata.data?.categories ?? [];
  const categoryField = review?.review_fields.find((field) => field.field_name === "category") ?? null;
  const currentCategory =
    asString(categoryField?.current_state.canonical_value ?? null) ??
    asString(categoryField?.suggested_state?.canonical_value ?? null);

  useEffect(() => {
    const nextTitle = review?.review_fields.find((field) => field.field_name === "title");
    const nextBrand = review?.review_fields.find((field) => field.field_name === "brand");
    setTitleInput(asString(nextTitle?.current_state.canonical_value ?? null) ?? "");
    setBrandInput(asString(nextBrand?.current_state.canonical_value ?? null) ?? "");
  }, [review?.review_version]);

  async function applyFieldChange(change: ClosetReviewFieldChange) {
    setNotice(null);
    const result = await reviewFlow.applyChanges([change]);
    if (result.ok) {
      await Haptics.selectionAsync();
      return;
    }

    if (result.stale) {
      setNotice("The review changed on the server, so Tenue reloaded the latest snapshot.");
    }
  }

  async function saveTextField(fieldName: "title" | "brand", value: string) {
    const normalized = value.trim();
    await applyFieldChange(
      normalized
        ? {
            field_name: fieldName,
            operation: "set_value",
            canonical_value: normalized
          }
        : {
            field_name: fieldName,
            operation: "clear"
          }
    );
  }

  function openSheet(field: ClosetReviewFieldSnapshot) {
    const multi = ["colors", "style_tags", "occasion_tags", "season_tags"].includes(field.field_name);
    const selected = multi
      ? asStringArray(field.current_state.canonical_value)
      : [asString(field.current_state.canonical_value) ?? ""].filter(Boolean);

    setSheet({
      fieldName: field.field_name,
      multi,
      options: selectionOptionsForField(field.field_name, categories, metadata.data, currentCategory),
      selected,
      title: field.field_name.replaceAll("_", " ")
    });
  }

  async function applySheetSelection() {
    if (!sheet) {
      return;
    }

    const normalizedSelection = sheet.selected.filter(Boolean);
    await applyFieldChange(
      normalizedSelection.length === 0
        ? {
            field_name: sheet.fieldName,
            operation: "clear"
          }
        : {
            field_name: sheet.fieldName,
            operation: "set_value",
            canonical_value: sheet.multi ? normalizedSelection : normalizedSelection[0]
          }
    );
    setSheet(null);
  }

  async function confirmItem() {
    setNotice(null);
    const result = await reviewFlow.confirm();

    if (result.ok) {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      return;
    }

    if (result.stale) {
      setNotice("The review version changed. Tenue refreshed the latest server state.");
      return;
    }

    await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
  }

  async function retryItem() {
    const success = await reviewFlow.retry(review?.retry_action.default_step);
    if (success) {
      await Haptics.selectionAsync();
    } else {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
  }

  const previewImage = review
    ? getReviewItemPreview(review)
    : reviewFlow.processing
      ? getReviewItemPreview(reviewFlow.processing)
      : null;
  const requiredFields = review
    ? ["category", "subcategory"]
        .map((fieldName) => review.review_fields.find((field) => field.field_name === fieldName))
        .filter((field): field is ClosetReviewFieldSnapshot => Boolean(field))
    : [];
  const optionalFields = review
    ? CLOSET_FIELD_ORDER.filter((fieldName) => !["category", "subcategory"].includes(fieldName))
        .map((fieldName) => review.review_fields.find((field) => field.field_name === fieldName))
        .filter((field): field is ClosetReviewFieldSnapshot => Boolean(field))
    : [];
  const rail = getReviewRail(review, reviewFlow.processing);
  const heroTitle =
    titleInput.trim() ||
    review?.review_fields.find((field) => field.field_name === "subcategory")?.suggested_state?.canonical_value ||
    "Review this closet item";

  return (
    <Screen
      footer={
        review?.lifecycle_status === "confirmed" ? (
          <Button label="Open in Closet" onPress={() => router.replace(`/closet/${itemId}` as Href)} tone="organize" />
        ) : (
          <Button
            label="Confirm Item"
            disabled={!review?.can_confirm || reviewFlow.isMutating}
            loading={reviewFlow.isMutating}
            onPress={() => void confirmItem()}
            tone="organize"
          />
        )
      }
    >
      <View style={styles.topRow}>
        <BrandMark variant="wordmark" subtle />
        <Button label="Queue" onPress={() => router.replace("/review" as Href)} size="sm" variant="secondary" />
      </View>

      {reviewFlow.isLoading ? (
        <>
          <SkeletonBlock height={340} />
          <SkeletonBlock height={160} />
          <SkeletonBlock height={220} />
        </>
      ) : (
        <>
          <Card tone={review?.lifecycle_status === "confirmed" ? "positive" : "review"} style={styles.heroCard}>
            {previewImage?.url ? (
              <Image source={{ uri: previewImage.url }} style={styles.heroImage} contentFit="contain" />
            ) : (
              <View style={[styles.heroImage, styles.imageFallback]} />
            )}

            <View style={styles.railRow}>
              {rail.map((step) => (
                <View key={step.key} style={styles.railStep}>
                  <Chip label={humanizeStatus(step.status)} tone={getStatusChipTone(step.status)} />
                  <AppText color={colors.textSubtle} variant="caption">
                    {step.label}
                  </AppText>
                </View>
              ))}
            </View>

            <View style={styles.statusStack}>
              <Chip
                label={humanizeStatus(review?.review_status ?? reviewFlow.processing?.processing_status)}
                tone={getStatusChipTone(review?.review_status ?? reviewFlow.processing?.processing_status ?? "pending")}
              />
              <AppText variant="display">{typeof heroTitle === "string" ? heroTitle : "Review this item"}</AppText>
              <AppText color={colors.textMuted}>
                {review?.failure_summary ??
                  review?.retry_action.reason ??
                  reviewFlow.processing?.failure_summary ??
                  "Required fields come first. Optional refinements stay beneath them so confirmation never feels like noisy form work."}
              </AppText>
            </View>
          </Card>

          {notice ? (
            <Card tone="lookbook">
              <AppText color={colors.warning}>{notice}</AppText>
            </Card>
          ) : null}

          {reviewFlow.error ? (
            <Card tone="lookbook">
              <AppText color={colors.danger}>{reviewFlow.error}</AppText>
            </Card>
          ) : null}

          {review?.retry_action.can_retry ? (
            <Card tone="lookbook">
              <AppText color={colors.textSubtle} variant="eyebrow">
                Retry
              </AppText>
              <AppText variant="sectionTitle">{getRetryStepLabel(review.retry_action.default_step)}</AppText>
              <AppText color={colors.textMuted}>
                {review.retry_action.reason ?? "Tenue can retry the failed step without losing the draft item."}
              </AppText>
              <Button
                label={getRetryStepLabel(review.retry_action.default_step)}
                onPress={() => void retryItem()}
                variant="secondary"
              />
            </Card>
          ) : null}

          {review ? (
            <>
              <Card tone="review">
                <AppText color={colors.textSubtle} variant="eyebrow">
                  Required fields
                </AppText>
                <AppText variant="sectionTitle">These are the gate before closet truth.</AppText>
                <View style={styles.fieldStack}>
                  {requiredFields.map((field) => (
                    <ReviewFieldRow
                      key={field.field_name}
                      field={field}
                      metadataReady={Boolean(metadata.data)}
                      onAcceptSuggestion={() =>
                        void applyFieldChange({
                          field_name: field.field_name,
                          operation: "accept_suggestion"
                        })
                      }
                      onClear={() =>
                        void applyFieldChange({
                          field_name: field.field_name,
                          operation: "clear"
                        })
                      }
                      onMarkNotApplicable={() =>
                        void applyFieldChange({
                          field_name: field.field_name,
                          operation: "mark_not_applicable"
                        })
                      }
                      onOpenSheet={() => openSheet(field)}
                    />
                  ))}
                </View>
              </Card>

              <Card tone="soft">
                <AppText color={colors.textSubtle} variant="eyebrow">
                  Suggested title
                </AppText>
                <TextField
                  label="Title"
                  placeholder="Black tee"
                  value={titleInput}
                  onChangeText={setTitleInput}
                />
                <View style={styles.actionRow}>
                  <Button
                    label="Save title"
                    onPress={() => void saveTextField("title", titleInput)}
                    size="sm"
                    variant="secondary"
                  />
                  {review.review_fields.find((field) => field.field_name === "title")?.suggested_state ? (
                    <ActionPill
                      label="Use suggestion"
                      onPress={() =>
                        void applyFieldChange({
                          field_name: "title",
                          operation: "accept_suggestion"
                        })
                      }
                    />
                  ) : null}
                  <ActionPill
                    label="Clear"
                    onPress={() =>
                      void applyFieldChange({
                        field_name: "title",
                        operation: "clear"
                      })
                    }
                  />
                </View>

                <TextField
                  label="Brand"
                  placeholder="Brand"
                  value={brandInput}
                  onChangeText={setBrandInput}
                />
                <View style={styles.actionRow}>
                  <Button
                    label="Save brand"
                    onPress={() => void saveTextField("brand", brandInput)}
                    size="sm"
                    variant="secondary"
                  />
                  {review.review_fields.find((field) => field.field_name === "brand")?.suggested_state ? (
                    <ActionPill
                      label="Use suggestion"
                      onPress={() =>
                        void applyFieldChange({
                          field_name: "brand",
                          operation: "accept_suggestion"
                        })
                      }
                    />
                  ) : null}
                  <ActionPill
                    label="Not applicable"
                    onPress={() =>
                      void applyFieldChange({
                        field_name: "brand",
                        operation: "mark_not_applicable"
                      })
                    }
                  />
                </View>
              </Card>

              <Card tone="soft">
                <AppText color={colors.textSubtle} variant="eyebrow">
                  Suggested attributes
                </AppText>
                <AppText variant="sectionTitle">Optional details stay calm and editable.</AppText>
                <View style={styles.fieldStack}>
                  {optionalFields
                    .filter((field) => !["title", "brand"].includes(field.field_name))
                    .map((field) => (
                      <ReviewFieldRow
                        key={field.field_name}
                        field={field}
                        metadataReady={Boolean(metadata.data)}
                        onAcceptSuggestion={() =>
                          void applyFieldChange({
                            field_name: field.field_name,
                            operation: "accept_suggestion"
                          })
                        }
                        onClear={() =>
                          void applyFieldChange({
                            field_name: field.field_name,
                            operation: "clear"
                          })
                        }
                        onMarkNotApplicable={() =>
                          void applyFieldChange({
                            field_name: field.field_name,
                            operation: "mark_not_applicable"
                          })
                        }
                        onOpenSheet={() => openSheet(field)}
                      />
                    ))}
                </View>
              </Card>
            </>
          ) : (
            <Card tone="review">
              <AppText color={colors.textSubtle} variant="eyebrow">
                Waiting on backend processing
              </AppText>
              <AppText color={colors.textMuted}>
                Tenue will keep polling until review becomes available or a retryable issue shows up.
              </AppText>
            </Card>
          )}
        </>
      )}

      <ModalSheet
        visible={Boolean(sheet)}
        onClose={() => setSheet(null)}
        footer={<Button label="Apply selection" onPress={() => void applySheetSelection()} tone="organize" />}
      >
        <AppText variant="title">{sheet?.title}</AppText>
        <ScrollView showsVerticalScrollIndicator={false} style={styles.sheetOptions}>
          <View style={styles.optionList}>
            {sheet?.options.map((option) => {
              const selected = sheet.selected.includes(option);

              return (
                <Pressable
                  key={option}
                  onPress={() => {
                    if (!sheet) {
                      return;
                    }

                    if (sheet.multi) {
                      setSheet({
                        ...sheet,
                        selected: selected
                          ? sheet.selected.filter((value) => value !== option)
                          : sheet.selected.concat(option)
                      });
                      return;
                    }

                    setSheet({
                      ...sheet,
                      selected: [option]
                    });
                  }}
                  style={[styles.optionButton, selected ? styles.optionButtonSelected : null]}
                >
                  <AppText color={selected ? colors.text : colors.textMuted} variant="bodyStrong">
                    {option}
                  </AppText>
                </Pressable>
              );
            })}
          </View>
        </ScrollView>
      </ModalSheet>
    </Screen>
  );
}

function ReviewFieldRow({
  field,
  metadataReady,
  onAcceptSuggestion,
  onClear,
  onMarkNotApplicable,
  onOpenSheet
}: {
  field: ClosetReviewFieldSnapshot;
  metadataReady: boolean;
  onAcceptSuggestion: () => void;
  onClear: () => void;
  onMarkNotApplicable: () => void;
  onOpenSheet: () => void;
}) {
  const suggestionValue = field.suggested_state ? formatFieldValue(field.suggested_state.canonical_value) : null;
  const fieldState = getReviewFieldStateLabel(field);
  const fieldHelper = buildReviewFieldHelper(field);

  return (
    <View style={styles.fieldRow}>
      <View style={styles.inlineBetween}>
        <View style={styles.fieldHeaderCopy}>
          <AppText variant="bodyStrong">{field.field_name.replaceAll("_", " ")}</AppText>
          {fieldHelper ? (
            <AppText color={colors.textSubtle} variant="caption">
              {fieldHelper}
            </AppText>
          ) : null}
        </View>
        <View style={styles.fieldHeaderBadges}>
          {field.required ? <Chip label="Required" tone="warning" /> : null}
          <Chip label={fieldState} tone={getReviewFieldStateTone(field)} />
        </View>
      </View>

      <Pressable onPress={onOpenSheet} style={styles.valueSurface}>
        <AppText variant="cardTitle">{currentValueLabel(field)}</AppText>
        <AppText color={colors.textSubtle} variant="captionStrong">
          Edit
        </AppText>
      </Pressable>

      {field.suggested_state ? (
        <View style={styles.suggestionBox}>
          <AppText color={colors.textSubtle} variant="caption">
            Suggested
          </AppText>
          <AppText variant="bodyStrong">
            {suggestionValue ?? humanizeStatus(field.suggested_state.applicability_state)}
          </AppText>
        </View>
      ) : null}

      <View style={styles.actionRow}>
        <Button
          label="Edit"
          onPress={onOpenSheet}
          variant="secondary"
          size="sm"
          disabled={!metadataReady}
        />
        {field.suggested_state ? <ActionPill label="Use suggestion" onPress={onAcceptSuggestion} /> : null}
        <ActionPill label="Clear" onPress={onClear} />
        {!field.required ? <ActionPill label="Not applicable" onPress={onMarkNotApplicable} /> : null}
      </View>
    </View>
  );
}

function ActionPill({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={styles.actionPill}>
      <AppText color={colors.text} variant="captionStrong">
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  heroCard: {
    gap: spacing.md
  },
  heroImage: {
    width: "100%",
    height: 300,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundMuted
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: colors.border
  },
  railRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  railStep: {
    width: "47%",
    gap: spacing.xs
  },
  statusStack: {
    gap: spacing.sm
  },
  fieldStack: {
    gap: spacing.lg
  },
  fieldRow: {
    gap: spacing.sm,
    paddingBottom: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border
  },
  fieldHeaderCopy: {
    flex: 1,
    gap: spacing.xs
  },
  fieldHeaderBadges: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: spacing.xs
  },
  inlineBetween: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: spacing.md
  },
  valueSurface: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.xs
  },
  suggestionBox: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundSoft,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.xs
  },
  actionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  actionPill: {
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft
  },
  sheetOptions: {
    maxHeight: 360
  },
  optionList: {
    gap: spacing.sm,
    paddingBottom: spacing.md
  },
  optionButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  },
  optionButtonSelected: {
    backgroundColor: colors.cornflowerSurface,
    borderColor: "rgba(174, 197, 241, 0.62)"
  }
});
