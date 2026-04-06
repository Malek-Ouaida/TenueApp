import { Image } from "expo-image";
import { router, type Href } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useReviewQueue } from "../../../src/closet/hooks";
import { getDraftPrimaryImage, getStatusChipTone } from "../../../src/closet/status";
import { formatRelativeDate } from "../../../src/lib/format";
import { colors, radius, spacing } from "../../../src/theme";
import { AppText, BrandMark, Button, Card, Chip, EmptyState, Screen, SkeletonBlock } from "../../../src/ui";

const sectionTones = {
  needs_review: "review",
  processing: "organize",
  needs_attention: "lookbook"
} as const;

export default function ReviewQueueScreen() {
  const { session } = useAuth();
  const reviewQueue = useReviewQueue(session?.access_token);

  return (
    <Screen>
      <View style={styles.topRow}>
        <BrandMark variant="wordmark" subtle />
        <Button label="Home" onPress={() => router.replace("/" as Href)} size="sm" variant="secondary" />
      </View>

      <Card tone="review">
        <AppText color={colors.textSubtle} variant="eyebrow">
          Review Inbox
        </AppText>
        <AppText variant="display">Everything needing judgment before it earns closet status.</AppText>
        <AppText color={colors.textMuted}>
          Processing, retry states, and editable review rows stay here. Confirmed items leave this
          surface entirely.
        </AppText>
      </Card>

      {reviewQueue.isLoading ? (
        <>
          <SkeletonBlock height={220} />
          <SkeletonBlock height={220} />
        </>
      ) : reviewQueue.items.length === 0 ? (
        <Card tone="review">
          <EmptyState
            eyebrow="Review"
            title="Your review queue is clear."
            copy="When you add a new item it will move through processing here until you confirm it into the closet."
            action={<Button label="Add to Closet" onPress={() => router.push("/add" as Href)} tone="organize" />}
          />
        </Card>
      ) : (
        reviewQueue.sections.map((section) => (
          <View key={section.key} style={styles.section}>
            <View style={styles.sectionHeader}>
              <View style={styles.sectionCopy}>
                <AppText color={colors.textSubtle} variant="eyebrow">
                  {section.title}
                </AppText>
                <AppText variant="sectionTitle">
                  {section.key === "needs_review"
                    ? "Ready for careful confirmation."
                    : section.key === "processing"
                      ? "System work still underway."
                      : "Something needs another pass."}
                </AppText>
              </View>
              <Chip label={`${section.items.length}`} tone={sectionTones[section.key]} />
            </View>

            {section.items.map((item) => (
              <Pressable
                key={item.id}
                onPress={() => router.push(`/review/${item.id}` as Href)}
              >
                <Card style={styles.itemCard} tone={sectionTones[section.key]}>
                  {getDraftPrimaryImage(item)?.url ? (
                    <Image
                      source={{ uri: getDraftPrimaryImage(item)?.url }}
                      style={styles.itemImage}
                      contentFit="cover"
                    />
                  ) : (
                    <View style={[styles.itemImage, styles.imageFallback]} />
                  )}
                  <View style={styles.itemBody}>
                    <View style={styles.inlineBetween}>
                      <Chip
                        label={
                          item.failure_summary
                            ? "Needs attention"
                            : item.review_status === "ready_to_confirm"
                              ? "Ready to confirm"
                              : item.lifecycle_status === "processing"
                                ? "Processing"
                                : "Needs review"
                        }
                        tone={getStatusChipTone(item.failure_summary ? "failed" : item.processing_status)}
                      />
                      <AppText color={colors.textSubtle} variant="caption">
                        {formatRelativeDate(item.updated_at)}
                      </AppText>
                    </View>
                    <AppText variant="cardTitle">
                      {item.title ?? "Untitled closet item"}
                    </AppText>
                    <AppText color={colors.textMuted}>
                      {item.failure_summary ??
                        "Open the item to inspect progress, accept or override suggestions, and confirm it into the closet."}
                    </AppText>
                  </View>
                </Card>
              </Pressable>
            ))}
          </View>
        ))
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  section: {
    gap: spacing.md
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
  itemCard: {
    gap: spacing.md
  },
  itemImage: {
    width: "100%",
    height: 220,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundMuted
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: colors.border
  },
  itemBody: {
    gap: spacing.sm
  },
  inlineBetween: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md
  }
});
