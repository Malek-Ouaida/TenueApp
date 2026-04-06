import { Image } from "expo-image";
import * as Haptics from "expo-haptics";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useClosetItemDetail, useClosetSimilarity } from "../../../src/closet/hooks";
import {
  buildProjectionMeta,
  formatFieldValue,
  getConfirmedItemPreview
} from "../../../src/closet/status";
import { formatRelativeDate, formatScore } from "../../../src/lib/format";
import { colors, radius, spacing } from "../../../src/theme";
import { AppText, BrandMark, Button, Card, Chip, Screen, SkeletonBlock } from "../../../src/ui";

export default function ClosetItemDetailScreen() {
  const params = useLocalSearchParams<{ itemId: string | string[] }>();
  const itemId = Array.isArray(params.itemId) ? params.itemId[0] : params.itemId;
  const { session } = useAuth();
  const detail = useClosetItemDetail(session?.access_token, itemId);
  const duplicates = useClosetSimilarity(session?.access_token, itemId, "duplicates");
  const similar = useClosetSimilarity(session?.access_token, itemId, "similar");
  const [showOriginal, setShowOriginal] = useState(false);

  async function archiveItem() {
    const archived = await detail.archive();
    if (!archived) {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      return;
    }

    await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    router.replace("/closet" as Href);
  }

  const heroImage = detail.detail
    ? showOriginal
      ? detail.detail.original_image ?? getConfirmedItemPreview(detail.detail)
      : getConfirmedItemPreview(detail.detail)
    : null;
  const provenanceSummary = detail.detail
    ? {
        confirmed: detail.detail.field_states.filter((field) => field.review_state === "user_confirmed").length,
        edited: detail.detail.field_states.filter((field) => field.review_state === "user_edited").length
      }
    : null;

  return (
    <Screen
      footer={
        <Button
          label="Archive Item"
          loading={detail.isArchiving}
          onPress={() => void archiveItem()}
          variant="secondary"
        />
      }
    >
      <View style={styles.topRow}>
        <BrandMark variant="wordmark" subtle />
        <Button label="Back" onPress={() => router.replace("/closet" as Href)} size="sm" variant="secondary" />
      </View>

      {detail.isLoading ? (
        <>
          <SkeletonBlock height={360} />
          <SkeletonBlock height={170} />
          <SkeletonBlock height={200} />
        </>
      ) : detail.detail ? (
        <>
          <Card tone="soft" style={styles.heroCard}>
            {heroImage?.url ? (
              <Image source={{ uri: heroImage.url }} style={styles.heroImage} contentFit="contain" />
            ) : (
              <View style={[styles.heroImage, styles.imageFallback]} />
            )}
            <View style={styles.heroControls}>
              <Chip label={showOriginal ? "Original" : "Processed first"} tone="organize" />
              {detail.detail.original_image ? (
                <Pressable onPress={() => setShowOriginal((current) => !current)}>
                  <AppText color={colors.text} variant="captionStrong">
                    {showOriginal ? "Show processed" : "Show original"}
                  </AppText>
                </Pressable>
              ) : null}
            </View>
            <AppText variant="display">
              {detail.detail.metadata_projection.title ??
                detail.detail.metadata_projection.subcategory ??
                "Confirmed item"}
            </AppText>
            <AppText color={colors.textMuted}>
              {buildProjectionMeta(detail.detail.metadata_projection) ?? "Confirmed metadata"}
            </AppText>
            <View style={styles.metaChips}>
              {[
                detail.detail.metadata_projection.category,
                detail.detail.metadata_projection.subcategory,
                detail.detail.metadata_projection.primary_color,
                detail.detail.metadata_projection.material,
                detail.detail.metadata_projection.brand
              ]
                .filter((value): value is string => Boolean(value))
                .map((value) => (
                  <Chip key={value} label={value} tone="organize" />
                ))}
            </View>
          </Card>

          <Card tone="soft">
            <AppText color={colors.textSubtle} variant="eyebrow">
              Trust & provenance
            </AppText>
            <View style={styles.statRow}>
              <DetailStat label="Confirmed" value={`${provenanceSummary?.confirmed ?? 0}`} />
              <DetailStat label="Edited" value={`${provenanceSummary?.edited ?? 0}`} />
              <DetailStat label="Confirmed at" value={formatRelativeDate(detail.detail.confirmed_at)} />
            </View>
            <AppText color={colors.textMuted}>
              Original imagery remains available for trust, but processed imagery leads the closet
              browsing experience.
            </AppText>
          </Card>

          <Card tone="soft">
            <AppText color={colors.textSubtle} variant="eyebrow">
              Confirmed details
            </AppText>
            <View style={styles.fieldGrid}>
              {[
                ["Category", detail.detail.metadata_projection.category],
                ["Subcategory", detail.detail.metadata_projection.subcategory],
                ["Primary color", detail.detail.metadata_projection.primary_color],
                ["Secondary colors", detail.detail.metadata_projection.secondary_colors?.join(", ") ?? null],
                ["Material", detail.detail.metadata_projection.material],
                ["Pattern", detail.detail.metadata_projection.pattern],
                ["Brand", detail.detail.metadata_projection.brand],
                ["Style tags", formatFieldValue(detail.detail.metadata_projection.style_tags ?? null)],
                ["Occasion tags", formatFieldValue(detail.detail.metadata_projection.occasion_tags ?? null)],
                ["Season tags", formatFieldValue(detail.detail.metadata_projection.season_tags ?? null)]
              ]
                .filter(([, value]) => Boolean(value))
                .map(([label, value]) => (
                  <View key={label} style={styles.fieldTile}>
                    <AppText color={colors.textSubtle} variant="caption">
                      {label}
                    </AppText>
                    <AppText variant="bodyStrong">{value}</AppText>
                  </View>
                ))}
            </View>
          </Card>

          <Card tone="spotlight">
            <AppText color={colors.textSubtle} variant="eyebrow">
              Duplicate candidates
            </AppText>
            {duplicates.isLoading ? (
              <SkeletonBlock height={124} />
            ) : duplicates.items.length ? (
              <View style={styles.relatedList}>
                {duplicates.items.map((item) => (
                  <View key={item.edge_id} style={styles.relatedCard}>
                    {item.other_item.display_image?.url ?? item.other_item.thumbnail_image?.url ? (
                      <Image
                        source={{
                          uri: item.other_item.display_image?.url ?? item.other_item.thumbnail_image?.url ?? undefined
                        }}
                        style={styles.relatedImage}
                        contentFit="cover"
                      />
                    ) : (
                      <View style={[styles.relatedImage, styles.imageFallback]} />
                    )}
                    <View style={styles.relatedBody}>
                      <View style={styles.inlineBetween}>
                        <AppText variant="bodyStrong">
                          {item.other_item.title ?? item.label}
                        </AppText>
                        <Chip label={formatScore(item.score)} tone="spotlight" />
                      </View>
                      <AppText color={colors.textMuted} variant="caption">
                        {item.label}
                      </AppText>
                      <View style={styles.chipRow}>
                        {item.signals.slice(0, 3).map((signal) => (
                          <Chip key={signal.code} label={signal.label} tone="muted" />
                        ))}
                      </View>
                      <View style={styles.actionRow}>
                        <Button
                          label="Dismiss"
                          onPress={() => void duplicates.applyEdgeAction(item.edge_id, "dismiss")}
                          size="sm"
                          variant="secondary"
                        />
                        <Button
                          label="Mark duplicate"
                          onPress={() => void duplicates.applyEdgeAction(item.edge_id, "mark_duplicate")}
                          size="sm"
                          tone="organize"
                        />
                      </View>
                    </View>
                  </View>
                ))}
              </View>
            ) : (
              <AppText color={colors.textMuted}>
                No duplicate candidates are currently attached to this item.
              </AppText>
            )}
          </Card>

          <Card tone="organize">
            <AppText color={colors.textSubtle} variant="eyebrow">
              Similar items
            </AppText>
            {similar.isLoading ? (
              <SkeletonBlock height={124} />
            ) : similar.items.length ? (
              <View style={styles.relatedList}>
                {similar.items.map((item) => (
                  <Pressable
                    key={item.edge_id}
                    onPress={() => router.push(`/closet/${item.other_item.item_id}` as Href)}
                    style={styles.relatedCard}
                  >
                    {item.other_item.display_image?.url ?? item.other_item.thumbnail_image?.url ? (
                      <Image
                        source={{
                          uri: item.other_item.display_image?.url ?? item.other_item.thumbnail_image?.url ?? undefined
                        }}
                        style={styles.relatedImage}
                        contentFit="cover"
                      />
                    ) : (
                      <View style={[styles.relatedImage, styles.imageFallback]} />
                    )}
                    <View style={styles.relatedBody}>
                      <View style={styles.inlineBetween}>
                        <AppText variant="bodyStrong">
                          {item.other_item.title ?? item.label}
                        </AppText>
                        <Chip label={formatScore(item.score)} tone="organize" />
                      </View>
                      <AppText color={colors.textMuted} variant="caption">
                        {item.label}
                      </AppText>
                      <View style={styles.chipRow}>
                        {item.signals.slice(0, 3).map((signal) => (
                          <Chip key={signal.code} label={signal.label} tone="muted" />
                        ))}
                      </View>
                    </View>
                  </Pressable>
                ))}
              </View>
            ) : (
              <AppText color={colors.textMuted}>
                Similar items will appear here after the backend recomputes similarity.
              </AppText>
            )}
          </Card>
        </>
      ) : (
        <Card tone="lookbook">
          <AppText color={colors.danger}>The confirmed item could not be loaded.</AppText>
        </Card>
      )}
    </Screen>
  );
}

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.statTile}>
      <AppText color={colors.textSubtle} variant="caption">
        {label}
      </AppText>
      <AppText numberOfLines={1} variant="bodyStrong">
        {value}
      </AppText>
    </View>
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
    height: 340,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundMuted
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: colors.border
  },
  heroControls: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md
  },
  metaChips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  statRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  statTile: {
    width: "30%",
    gap: spacing.xs
  },
  fieldGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  fieldTile: {
    width: "47%",
    gap: spacing.xs
  },
  relatedList: {
    gap: spacing.md,
    marginTop: spacing.sm
  },
  relatedCard: {
    flexDirection: "row",
    gap: spacing.md
  },
  relatedImage: {
    width: 96,
    height: 112,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundMuted
  },
  relatedBody: {
    flex: 1,
    gap: spacing.sm
  },
  inlineBetween: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs
  },
  actionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  }
});
