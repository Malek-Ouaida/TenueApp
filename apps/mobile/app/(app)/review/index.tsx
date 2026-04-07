import { Feather } from "@expo/vector-icons";
import { router, type Href } from "expo-router";
import { useEffect, useMemo } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useReviewQueue } from "../../../src/closet/hooks";
import { isReviewableDraft } from "../../../src/closet/status";
import { usePolling } from "../../../src/lib/hooks";
import { fontFamilies } from "../../../src/theme";
import { AppText, SkeletonBlock } from "../../../src/ui";

const palette = {
  background: "#FAF9F7",
  surface: "#FFFFFF",
  text: "#0F172A",
  muted: "#94A3B8",
  warmGray: "#64748B",
  border: "#E2E8F0",
  secondary: "#F8F8F6",
  lavender: "#E8DBFF",
  shadow: "rgba(15, 23, 42, 0.08)"
} as const;

function ReviewLoadingScreen() {
  return (
    <View style={styles.loadingScreen}>
      <SkeletonBlock height={80} />
      <SkeletonBlock height={540} />
    </View>
  );
}

export default function ReviewQueueScreen() {
  const { session } = useAuth();
  const reviewQueue = useReviewQueue(session?.access_token, 50);

  const reviewableItems = useMemo(
    () => reviewQueue.items.filter(isReviewableDraft),
    [reviewQueue.items]
  );
  const firstReviewableId = reviewableItems[0]?.id ?? null;
  const processingCount =
    reviewQueue.sections.find((section) => section.key === "processing")?.items.length ?? 0;
  const backlogSections = reviewQueue.sections.filter((section) => section.key !== "needs_review");

  usePolling(
    () => reviewQueue.refresh(),
    processingCount > 0 && reviewableItems.length === 0,
    3000
  );

  useEffect(() => {
    if (firstReviewableId) {
      router.replace(`/review/${firstReviewableId}` as Href);
    }
  }, [firstReviewableId]);

  useEffect(() => {
    if (!reviewQueue.isLoading && !firstReviewableId && backlogSections.length > 0) {
      router.replace("/closet?tab=processing" as Href);
    }
  }, [backlogSections.length, firstReviewableId, reviewQueue.isLoading]);

  if (reviewQueue.isLoading || firstReviewableId || backlogSections.length > 0) {
    return <ReviewLoadingScreen />;
  }

  return (
    <View style={styles.doneScreen}>
      <View style={styles.doneOrb}>
        <Feather color={palette.text} name="star" size={28} />
      </View>
      <AppText color={palette.text} style={styles.doneTitle}>
        {processingCount > 0 ? "Still processing" : "You're all set"}
      </AppText>
      <AppText color={palette.muted} style={styles.doneBody}>
        {processingCount > 0
          ? "Tenue is still working through your latest uploads. This page will update when items are ready to confirm."
          : "Everything in the review queue has been handled and added to your closet."}
      </AppText>
      <Pressable
        onPress={() => router.replace("/closet" as Href)}
        style={({ pressed }) => [styles.doneButton, pressed ? styles.pressed : null]}
      >
        <AppText color={palette.surface} style={styles.doneButtonLabel}>
          View Closet
        </AppText>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  loadingScreen: {
    flex: 1,
    backgroundColor: palette.background,
    paddingHorizontal: 24,
    paddingTop: 24,
    gap: 20
  },
  backlogScreen: {
    paddingHorizontal: 24,
    paddingTop: 18,
    paddingBottom: 32,
    gap: 20,
    backgroundColor: palette.background
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  headerButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: palette.surface,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 12,
    elevation: 4
  },
  headerCopy: {
    alignItems: "center",
    gap: 2
  },
  headerTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 16,
    lineHeight: 20
  },
  headerSubtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
  },
  headerSpacer: {
    width: 40
  },
  backlogIntro: {
    borderRadius: 24,
    backgroundColor: palette.surface,
    padding: 18,
    gap: 8,
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 14,
    elevation: 4
  },
  backlogTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 24,
    lineHeight: 28
  },
  backlogBody: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 20
  },
  backlogSection: {
    gap: 12
  },
  backlogSectionLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase"
  },
  backlogList: {
    gap: 12
  },
  backlogCard: {
    borderRadius: 20,
    backgroundColor: palette.surface,
    padding: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 14,
    elevation: 4
  },
  backlogImage: {
    width: 60,
    height: 76,
    borderRadius: 14,
    backgroundColor: palette.secondary
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: palette.border
  },
  backlogCopy: {
    flex: 1,
    gap: 4
  },
  backlogCardTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  backlogCardBody: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
  },
  backlogMeta: {
    alignItems: "flex-end",
    gap: 10
  },
  backlogStatusPill: {
    borderRadius: 999,
    backgroundColor: palette.secondary,
    paddingHorizontal: 10,
    paddingVertical: 6
  },
  backlogStatusLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14
  },
  doneScreen: {
    flex: 1,
    backgroundColor: palette.background,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32
  },
  doneOrb: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: palette.lavender,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 24
  },
  doneTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 32,
    lineHeight: 36,
    textAlign: "center"
  },
  doneBody: {
    marginTop: 12,
    textAlign: "center",
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 22
  },
  doneButton: {
    marginTop: 28,
    minHeight: 52,
    borderRadius: 26,
    backgroundColor: palette.text,
    minWidth: 180,
    alignItems: "center",
    justifyContent: "center"
  },
  doneButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  pressed: {
    opacity: 0.78
  }
});
