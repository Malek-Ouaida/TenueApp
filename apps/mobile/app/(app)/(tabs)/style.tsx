import { router, type Href } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useReviewQueue } from "../../../src/closet/hooks";
import { useClosetInsights } from "../../../src/closet/insights";
import { colors, spacing } from "../../../src/theme";
import { AppText, BrandMark, Button, Card, Chip, Screen } from "../../../src/ui";

export default function StyleScreen() {
  const { session } = useAuth();
  const reviewQueue = useReviewQueue(session?.access_token);
  const insights = useClosetInsights(session?.access_token);

  const needsReviewCount =
    reviewQueue.sections.find((section) => section.key === "needs_review")?.items.length ?? 0;
  const processingCount =
    reviewQueue.sections.find((section) => section.key === "processing")?.items.length ?? 0;
  const readiness = insights.insights.totalItems === 0 ? 8 : Math.min(92, 28 + insights.insights.totalItems * 9 - needsReviewCount * 6);

  return (
    <Screen>
      <BrandMark variant="wordmark" subtle />

      <Card tone="intelligence">
        <AppText color={colors.textSubtle} variant="eyebrow">
          Style
        </AppText>
        <AppText variant="display">This tab is the payoff, not the foundation.</AppText>
        <AppText color={colors.textMuted}>
          Tenue will earn stronger styling, buy-or-not, visual shopping, and try-on once the closet
          is confirmed and clean.
        </AppText>
        <View style={styles.actionRow}>
          <Button
            label="Clear Review"
            onPress={() => router.push("/review" as Href)}
            tone="review"
          />
          <Button
            label="Open Closet"
            onPress={() => router.push("/closet" as Href)}
            variant="secondary"
          />
        </View>
      </Card>

      <Card tone="soft" style={styles.readinessCard}>
        <View style={styles.inlineBetween}>
          <View style={styles.sectionCopy}>
            <AppText color={colors.textSubtle} variant="eyebrow">
              Closet readiness
            </AppText>
            <AppText variant="sectionTitle">How much real wardrobe signal exists today.</AppText>
          </View>
          <Chip label={`${Math.max(0, Math.min(100, readiness))}%`} tone="intelligence" />
        </View>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${Math.max(0, Math.min(100, readiness))}%` }]} />
        </View>
        <View style={styles.statGrid}>
          <StatTile label="Confirmed items" value={`${insights.insights.totalItems}`} />
          <StatTile label="Needs review" value={`${needsReviewCount}`} />
          <StatTile label="Processing" value={`${processingCount}`} />
          <StatTile
            label="Top category"
            value={insights.insights.topCategory?.label ?? "Waiting"}
          />
        </View>
      </Card>

      <View style={styles.featureGrid}>
        <FeatureCard
          copy="Outfit suggestions from confirmed wardrobe pieces, grounded in what you actually own."
          eyebrow="AI Stylist"
          tone="intelligence"
          title="Preparing on top of closet truth."
        />
        <FeatureCard
          copy="Compare a candidate item against your wardrobe fit, redundancy, and likely use."
          eyebrow="Should I Buy"
          tone="spotlight"
          title="Unlocks once closet depth is stronger."
        />
        <FeatureCard
          copy="Visual match and similar-item shopping will stay tied to closet relevance, not generic trend browsing."
          eyebrow="Shop the Look"
          tone="organize"
          title="Grounded shopping, not a feed."
        />
        <FeatureCard
          copy="Try-on stays behind a replaceable provider layer and only matters once owned and candidate items are trustworthy."
          eyebrow="Try-On"
          tone="lookbook"
          title="Polished shell, future provider hook."
        />
      </View>

      <Pressable onPress={() => router.push("/insights" as Href)}>
        <Card tone="soft">
          <AppText color={colors.textSubtle} variant="eyebrow">
            Insights
          </AppText>
          <AppText variant="sectionTitle">See the wardrobe patterns already emerging.</AppText>
          <AppText color={colors.textMuted}>
            Category mix, dominant colors, processed coverage, and backlog signals are already live
            from current APIs.
          </AppText>
        </Card>
      </Pressable>
    </Screen>
  );
}

function FeatureCard({
  copy,
  eyebrow,
  title,
  tone
}: {
  copy: string;
  eyebrow: string;
  title: string;
  tone: "intelligence" | "spotlight" | "organize" | "lookbook";
}) {
  return (
    <Card shadow={false} style={styles.featureCard} tone={tone}>
      <Chip label="Planned" tone={tone} />
      <AppText color={colors.textSubtle} variant="eyebrow">
        {eyebrow}
      </AppText>
      <AppText variant="cardTitle">{title}</AppText>
      <AppText color={colors.textMuted}>{copy}</AppText>
    </Card>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
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
  actionRow: {
    flexDirection: "row",
    gap: spacing.sm
  },
  readinessCard: {
    gap: spacing.md
  },
  inlineBetween: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.md
  },
  sectionCopy: {
    flex: 1,
    gap: spacing.xs
  },
  progressTrack: {
    height: 12,
    borderRadius: 999,
    backgroundColor: colors.backgroundMuted,
    overflow: "hidden"
  },
  progressFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: colors.purple
  },
  statGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  statTile: {
    width: "47%",
    gap: spacing.xs
  },
  featureGrid: {
    gap: spacing.sm
  },
  featureCard: {
    gap: spacing.sm
  }
});
