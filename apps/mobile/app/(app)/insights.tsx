import { router, type Href } from "expo-router";
import { Image } from "expo-image";
import { Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../src/auth/provider";
import { useConfirmedClosetBrowse, useClosetSimilarity, useReviewQueue } from "../../src/closet/hooks";
import { useClosetInsights } from "../../src/closet/insights";
import { colors, radius, spacing } from "../../src/theme";
import { AppText, BrandMark, Button, Card, Chip, Screen, SkeletonBlock } from "../../src/ui";

export default function InsightsScreen() {
  const { session } = useAuth();
  const insights = useClosetInsights(session?.access_token);
  const reviewQueue = useReviewQueue(session?.access_token);
  const confirmed = useConfirmedClosetBrowse(session?.access_token, {}, 4);
  const featuredItem = confirmed.items[0] ?? insights.items[0] ?? null;
  const duplicates = useClosetSimilarity(session?.access_token, featuredItem?.item_id, "duplicates");

  const needsReviewCount =
    reviewQueue.sections.find((section) => section.key === "needs_review")?.items.length ?? 0;
  const attentionCount =
    reviewQueue.sections.find((section) => section.key === "needs_attention")?.items.length ?? 0;
  const processedCoverage =
    insights.insights.totalItems === 0
      ? "0%"
      : `${Math.round((insights.insights.processedItems / insights.insights.totalItems) * 100)}%`;

  return (
    <Screen>
      <View style={styles.topRow}>
        <BrandMark variant="wordmark" subtle />
        <Button label="Back" onPress={() => router.back()} size="sm" variant="secondary" />
      </View>

      <Card tone="organize">
        <AppText color={colors.textSubtle} variant="eyebrow">
          Insights
        </AppText>
        <AppText variant="display">Luxury analytics for the wardrobe you are actually building.</AppText>
        <AppText color={colors.textMuted}>
          Every card here is derived from current closet contracts. No lookbook, wear-log, or style
          intelligence claims are being faked ahead of the product.
        </AppText>
      </Card>

      <View style={styles.metricsRow}>
        <MetricCard label="Closet items" value={`${insights.insights.totalItems}`} />
        <MetricCard label="Processed" value={processedCoverage} tone="positive" />
        <MetricCard label="Review backlog" value={`${needsReviewCount + attentionCount}`} tone="review" />
      </View>

      <InsightCard
        eyebrow="Category mix"
        tone="soft"
        title={insights.insights.topCategory?.label ?? "No dominant category yet"}
      >
        <AppText color={colors.textMuted}>
          {insights.insights.topCategory
            ? `${insights.insights.topCategory.count} pieces lead the wardrobe right now.`
            : "Confirm more pieces and the closet silhouette will start to emerge."}
        </AppText>
        <MixRow items={insights.insights.categoryMix.slice(0, 4)} tone="organize" />
      </InsightCard>

      <InsightCard
        eyebrow="Color signature"
        tone="lookbook"
        title={insights.insights.topColor?.label ?? "Color identity is still forming"}
      >
        <AppText color={colors.textMuted}>
          {insights.insights.topColor
            ? `${insights.insights.topColor.count} confirmed items anchor the leading palette.`
            : "Primary color trends will appear as soon as a few more items are confirmed."}
        </AppText>
        <MixRow items={insights.insights.colorMix.slice(0, 4)} tone="lookbook" />
      </InsightCard>

      <InsightCard
        eyebrow="Material mix"
        tone="spotlight"
        title={insights.insights.topMaterial?.label ?? "Material signal not ready"}
      >
        <AppText color={colors.textMuted}>
          Material tracking is already available off confirmed metadata, even before advanced closet
          insights land server-side.
        </AppText>
        <MixRow items={insights.insights.materialMix.slice(0, 4)} tone="spotlight" />
      </InsightCard>

      <InsightCard
        eyebrow="Duplicate watchlist"
        tone="intelligence"
        title={featuredItem?.title ?? "Confirm an item to inspect similarity"}
      >
        {confirmed.isLoading ? (
          <SkeletonBlock height={140} />
        ) : featuredItem ? (
          <View style={styles.duplicateRow}>
            {featuredItem.display_image?.url ?? featuredItem.thumbnail_image?.url ? (
              <Image
                source={{ uri: featuredItem.display_image?.url ?? featuredItem.thumbnail_image?.url ?? undefined }}
                style={styles.duplicateImage}
                contentFit="cover"
              />
            ) : (
              <View style={[styles.duplicateImage, styles.imageFallback]} />
            )}
            <View style={styles.duplicateCopy}>
              <AppText color={colors.textMuted}>
                {duplicates.items.length
                  ? `${duplicates.items.length} duplicate candidate${duplicates.items.length === 1 ? "" : "s"} are attached to the anchor piece.`
                  : "No duplicate candidates are currently attached to this item."}
              </AppText>
              <Pressable onPress={() => router.push(`/closet/${featuredItem.item_id}` as Href)}>
                <AppText color={colors.text} variant="captionStrong">
                  Open item detail
                </AppText>
              </Pressable>
            </View>
          </View>
        ) : (
          <AppText color={colors.textMuted}>
            Duplicate watchlists become meaningful after the first confirmed items arrive.
          </AppText>
        )}
      </InsightCard>
    </Screen>
  );
}

function InsightCard({
  children,
  eyebrow,
  title,
  tone
}: {
  children: React.ReactNode;
  eyebrow: string;
  title: string;
  tone: "soft" | "lookbook" | "spotlight" | "intelligence";
}) {
  return (
    <Card tone={tone}>
      <AppText color={colors.textSubtle} variant="eyebrow">
        {eyebrow}
      </AppText>
      <AppText variant="sectionTitle">{title}</AppText>
      <View style={styles.cardBody}>{children}</View>
    </Card>
  );
}

function MetricCard({
  label,
  tone = "soft",
  value
}: {
  label: string;
  tone?: "soft" | "positive" | "review";
  value: string;
}) {
  return (
    <Card shadow={false} style={styles.metricCard} tone={tone}>
      <AppText color={colors.textSubtle} variant="caption">
        {label}
      </AppText>
      <AppText variant="bodyStrong">{value}</AppText>
    </Card>
  );
}

function MixRow({
  items,
  tone
}: {
  items: Array<{ label: string; count: number }>;
  tone: "organize" | "lookbook" | "spotlight";
}) {
  return (
    <View style={styles.mixRow}>
      {items.map((item) => (
        <Chip key={item.label} label={`${item.label} · ${item.count}`} tone={tone} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  metricsRow: {
    flexDirection: "row",
    gap: spacing.sm
  },
  metricCard: {
    flex: 1,
    gap: spacing.xs
  },
  cardBody: {
    gap: spacing.sm
  },
  mixRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  duplicateRow: {
    flexDirection: "row",
    gap: spacing.md
  },
  duplicateImage: {
    width: 96,
    height: 116,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundMuted
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: colors.border
  },
  duplicateCopy: {
    flex: 1,
    gap: spacing.sm
  }
});
