import { Image } from "expo-image";
import { router, type Href } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useConfirmedClosetBrowse, useClosetSimilarity, useReviewQueue } from "../../../src/closet/hooks";
import { useClosetInsights } from "../../../src/closet/insights";
import { getDraftPrimaryImage, getStatusChipTone } from "../../../src/closet/status";
import { formatRelativeDate } from "../../../src/lib/format";
import { colors, radius, spacing } from "../../../src/theme";
import {
  AppText,
  BrandMark,
  Button,
  Card,
  Chip,
  EmptyState,
  Screen,
  SkeletonBlock
} from "../../../src/ui";

export default function HomeScreen() {
  const { session, user } = useAuth();
  const reviewQueue = useReviewQueue(session?.access_token);
  const closetPreview = useConfirmedClosetBrowse(session?.access_token, {}, 6);
  const insights = useClosetInsights(session?.access_token);

  const spotlight =
    reviewQueue.sections.find((section) => section.key === "needs_review")?.items[0] ??
    reviewQueue.sections[0]?.items[0] ??
    null;
  const firstConfirmedItem = closetPreview.items[0] ?? insights.items[0] ?? null;
  const duplicatePreview = useClosetSimilarity(
    session?.access_token,
    firstConfirmedItem?.item_id,
    "duplicates"
  );
  const similarPreview = useClosetSimilarity(
    session?.access_token,
    firstConfirmedItem?.item_id,
    "similar"
  );

  const needsReviewCount =
    reviewQueue.sections.find((section) => section.key === "needs_review")?.items.length ?? 0;
  const processingCount =
    reviewQueue.sections.find((section) => section.key === "processing")?.items.length ?? 0;
  const attentionCount =
    reviewQueue.sections.find((section) => section.key === "needs_attention")?.items.length ?? 0;

  const readinessLabel =
    insights.insights.totalItems === 0
      ? "Start by confirming the first item."
      : needsReviewCount > 0
        ? "Clear review to sharpen styling."
        : "Closet is ready for smarter suggestions.";

  const greetingName =
    user?.email?.split("@")[0]?.split(/[._-]/)[0]?.replace(/^./, (value) => value.toUpperCase()) ??
    "You";

  return (
    <Screen>
      <View style={styles.topRow}>
        <BrandMark />
        <Pressable
          onPress={() => router.push("/profile" as Href)}
          style={styles.avatar}
        >
          <AppText variant="bodyStrong">
            {(user?.email?.charAt(0) ?? "T").toUpperCase()}
          </AppText>
        </Pressable>
      </View>

      <Card tone="soft">
        <AppText color={colors.textSubtle} variant="eyebrow">
          Home
        </AppText>
        <AppText variant="display">{greetingName}, keep the closet clean.</AppText>
        <AppText color={colors.textMuted}>
          Review stays first. Confirmed items unlock search, duplicate detection, style help, and
          future intelligence without muddying the source of truth.
        </AppText>
        <View style={styles.heroActions}>
          <Button
            label="Add to Closet"
            onPress={() => router.push("/add" as Href)}
            tone="organize"
          />
          <Button
            label="Open Review"
            onPress={() => router.push("/review" as Href)}
            variant="secondary"
          />
        </View>
      </Card>

      <View style={styles.metricsRow}>
        <MetricCard label="Confirmed" value={`${insights.insights.totalItems}`} tone="soft" />
        <MetricCard label="Needs Review" value={`${needsReviewCount}`} tone="review" />
        <MetricCard label="Processing" value={`${processingCount + attentionCount}`} tone="organize" />
      </View>

      <SectionHeader
        actionLabel="Review inbox"
        eyebrow="Needs Review"
        onPress={() => router.push("/review" as Href)}
        title="The next item waiting on your judgment."
      />

      {reviewQueue.isLoading ? (
        <Card tone="review">
          <SkeletonBlock height={240} />
        </Card>
      ) : spotlight ? (
        <Pressable onPress={() => router.push(`/review/${spotlight.id}` as Href)}>
          <Card tone={spotlight.failure_summary ? "lookbook" : "review"} style={styles.spotlightCard}>
            {getDraftPrimaryImage(spotlight)?.url ? (
              <Image
                source={{ uri: getDraftPrimaryImage(spotlight)?.url }}
                style={styles.spotlightImage}
                contentFit="cover"
              />
            ) : (
              <View style={[styles.spotlightImage, styles.imageFallback]} />
            )}
            <View style={styles.spotlightBody}>
              <View style={styles.inlineBetween}>
                <Chip
                  label={
                    spotlight.failure_summary
                      ? "Needs attention"
                      : spotlight.review_status === "ready_to_confirm"
                        ? "Ready to confirm"
                        : "Needs review"
                  }
                  tone={getStatusChipTone(spotlight.failure_summary ? "failed" : spotlight.review_status)}
                />
                <AppText color={colors.textSubtle} variant="caption">
                  {formatRelativeDate(spotlight.updated_at)}
                </AppText>
              </View>
              <AppText variant="title">{spotlight.title ?? "Untitled closet item"}</AppText>
              <AppText color={colors.textMuted}>
                {spotlight.failure_summary ??
                  "Calmly confirm the essentials first: category and subcategory, then refine anything else that matters."}
              </AppText>
              <Button
                label="Review item"
                onPress={() => router.push(`/review/${spotlight.id}` as Href)}
                size="sm"
                tone="review"
              />
            </View>
          </Card>
        </Pressable>
      ) : (
        <Card tone="review">
          <EmptyState
            eyebrow="Review"
            title="Inbox is clear."
            copy="The next upload will land here until it is confirmed or needs another pass."
            action={<Button label="Add to Closet" onPress={() => router.push("/add" as Href)} tone="organize" />}
          />
        </Card>
      )}

      <View style={styles.splitRow}>
        <Pressable style={styles.splitColumn} onPress={() => router.push("/closet" as Href)}>
          <Card tone="soft" style={styles.fillCard}>
            <AppText color={colors.textSubtle} variant="eyebrow">
              Closet Snapshot
            </AppText>
            <AppText variant="sectionTitle">Confirmed pieces only.</AppText>
            <View style={styles.miniGrid}>
              {closetPreview.isLoading
                ? [0, 1, 2, 3].map((index) => (
                    <SkeletonBlock key={index} height={88} style={styles.miniTile} />
                  ))
                : (insights.insights.recentItems.length ? insights.insights.recentItems : closetPreview.items)
                    .slice(0, 4)
                    .map((item) =>
                      item.display_image?.url ?? item.thumbnail_image?.url ? (
                        <Image
                          key={item.item_id}
                          source={{ uri: item.display_image?.url ?? item.thumbnail_image?.url ?? undefined }}
                          style={styles.miniTile}
                          contentFit="cover"
                        />
                      ) : (
                        <View key={item.item_id} style={[styles.miniTile, styles.imageFallback]} />
                      )
                    )}
            </View>
            <AppText color={colors.textMuted}>
              {insights.insights.topCategory
                ? `${insights.insights.topCategory.label} leads right now.`
                : "Confirmed items will start composing the wardrobe here."}
            </AppText>
          </Card>
        </Pressable>

        <Pressable style={styles.splitColumn} onPress={() => router.push("/style" as Href)}>
          <Card tone="intelligence" style={styles.fillCard}>
            <AppText color={colors.textSubtle} variant="eyebrow">
              Style Intelligence
            </AppText>
            <AppText variant="sectionTitle">Payoff comes after trust.</AppText>
            <AppText color={colors.textMuted}>{readinessLabel}</AppText>
            <View style={styles.statStack}>
              <MetricLine label="Confirmed wardrobe" value={`${insights.insights.totalItems}`} />
              <MetricLine label="Ready to confirm" value={`${needsReviewCount}`} />
              <MetricLine label="Needs attention" value={`${attentionCount}`} />
            </View>
          </Card>
        </Pressable>
      </View>

      <View style={styles.splitRow}>
        <Pressable style={styles.splitColumn} onPress={() => router.push("/insights" as Href)}>
          <Card tone="organize" style={styles.fillCard}>
            <AppText color={colors.textSubtle} variant="eyebrow">
              Insights Preview
            </AppText>
            <AppText variant="sectionTitle">One elegant signal at a time.</AppText>
            {insights.isLoading ? (
              <SkeletonBlock height={118} />
            ) : (
              <View style={styles.statStack}>
                <MetricLine
                  label="Top category"
                  value={insights.insights.topCategory?.label ?? "Still empty"}
                />
                <MetricLine
                  label="Top color"
                  value={insights.insights.topColor?.label ?? "Awaiting pattern"}
                />
                <MetricLine
                  label="Material mix"
                  value={insights.insights.topMaterial?.label ?? "No material signal yet"}
                />
              </View>
            )}
          </Card>
        </Pressable>

        <Pressable
          style={styles.splitColumn}
          onPress={() =>
            firstConfirmedItem
              ? router.push(`/closet/${firstConfirmedItem.item_id}` as Href)
              : router.push("/closet" as Href)
          }
        >
          <Card tone="spotlight" style={styles.fillCard}>
            <AppText color={colors.textSubtle} variant="eyebrow">
              Duplicates / Similar
            </AppText>
            <AppText variant="sectionTitle">Similarity stays explainable.</AppText>
            <View style={styles.statStack}>
              <MetricLine
                label="Duplicate candidates"
                value={firstConfirmedItem ? `${duplicatePreview.items.length}` : "0"}
              />
              <MetricLine
                label="Similar items"
                value={firstConfirmedItem ? `${similarPreview.items.length}` : "0"}
              />
              <MetricLine
                label="Anchor item"
                value={firstConfirmedItem?.title ?? "Confirm items first"}
              />
            </View>
          </Card>
        </Pressable>
      </View>

      <Card tone="lookbook">
        <AppText color={colors.textSubtle} variant="eyebrow">
          Lookbook Preview
        </AppText>
        <AppText variant="sectionTitle">Separate from closet ingestion by design.</AppText>
        <AppText color={colors.textMuted}>
          Mirror outfits, styled looks, and inspiration images will live here once the lookbook
          flow is wired. This first pass protects that distinction instead of mixing everything into
          the closet.
        </AppText>
        <View style={styles.chipRow}>
          <Chip label="Mirror looks" tone="lookbook" />
          <Chip label="Outfit history" tone="lookbook" />
          <Chip label="Inspiration save" tone="lookbook" />
        </View>
      </Card>
    </Screen>
  );
}

function SectionHeader({
  actionLabel,
  eyebrow,
  onPress,
  title
}: {
  actionLabel: string;
  eyebrow: string;
  onPress: () => void;
  title: string;
}) {
  return (
    <View style={styles.sectionHeader}>
      <View style={styles.sectionCopy}>
        <AppText color={colors.textSubtle} variant="eyebrow">
          {eyebrow}
        </AppText>
        <AppText variant="sectionTitle">{title}</AppText>
      </View>
      <Pressable onPress={onPress}>
        <AppText color={colors.text} variant="captionStrong">
          {actionLabel}
        </AppText>
      </Pressable>
    </View>
  );
}

function MetricCard({
  label,
  tone,
  value
}: {
  label: string;
  tone: "soft" | "review" | "organize";
  value: string;
}) {
  return (
    <Card shadow={false} style={styles.metricCard} tone={tone}>
      <AppText color={colors.textSubtle} variant="captionStrong">
        {label}
      </AppText>
      <AppText variant="title">{value}</AppText>
    </Card>
  );
}

function MetricLine({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metricLine}>
      <AppText color={colors.textSubtle} variant="caption">
        {label}
      </AppText>
      <AppText numberOfLines={1} style={styles.metricValue} variant="bodyStrong">
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
  avatar: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  },
  heroActions: {
    flexDirection: "row",
    gap: spacing.sm
  },
  metricsRow: {
    flexDirection: "row",
    gap: spacing.sm
  },
  metricCard: {
    flex: 1,
    gap: spacing.xs
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.md
  },
  sectionCopy: {
    flex: 1,
    gap: spacing.xs
  },
  spotlightCard: {
    gap: spacing.lg
  },
  spotlightImage: {
    width: "100%",
    height: 260,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundMuted
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: colors.border
  },
  spotlightBody: {
    gap: spacing.sm
  },
  inlineBetween: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md
  },
  splitRow: {
    flexDirection: "row",
    gap: spacing.sm
  },
  splitColumn: {
    flex: 1
  },
  fillCard: {
    minHeight: 228,
    gap: spacing.sm
  },
  miniGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  miniTile: {
    width: "47%",
    height: 88,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundMuted
  },
  statStack: {
    gap: spacing.sm
  },
  metricLine: {
    gap: spacing.xs
  },
  metricValue: {
    flexShrink: 1
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  }
});
