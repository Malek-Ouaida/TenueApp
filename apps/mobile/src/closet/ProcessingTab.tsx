import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, type Href } from "expo-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { Animated, Easing, Pressable, StyleSheet, View } from "react-native";

import { fontFamilies } from "../theme";
import { AppText } from "../ui";
import { getDraftPrimaryImage } from "./status";
import type { ClosetDraftSnapshot, ClosetQueueSection } from "./types";

const palette = {
  cream: "#FAF9F7",
  warmWhite: "#FFFFFF",
  darkText: "#0F172A",
  warmGray: "#64748B",
  muted: "#94A3B8",
  border: "#E2E8F0",
  shadow: "rgba(15, 23, 42, 0.06)",
  sage: "#DCFCE7",
  sageText: "#166534",
  coral: "#FFD2C2",
  coralText: "#7C2D12",
  butter: "#FFEFA1",
  subtle: "#F8F8F6"
} as const;

type ProcessingTabProps = {
  onOpenItem: (itemId: string) => void;
  readyCount?: number;
  sections: ClosetQueueSection[];
};

type CompletedProcessingItem = {
  expiresAt: number;
  item: ClosetDraftSnapshot;
  progressFrom: number;
};

type ProcessingListItem = {
  initialProgress?: number;
  item: ClosetDraftSnapshot;
  sectionKey: ClosetQueueSection["key"];
};

type ProcessingVisualStatus = "analyzing" | "detecting" | "matching" | "ready" | "needs_attention";

const STATUS_LABELS: Record<ProcessingVisualStatus, string> = {
  analyzing: "Analyzing...",
  detecting: "Detecting items...",
  matching: "Finding matches...",
  ready: "Ready to confirm",
  needs_attention: "Needs attention"
};

function getVisualState(
  item: ClosetDraftSnapshot,
  sectionKey: ClosetQueueSection["key"]
): {
  progress: number;
  showProgress: boolean;
  status: ProcessingVisualStatus;
} {
  if (item.lifecycle_status === "review" || item.review_status === "ready_to_confirm") {
    return {
      progress: 100,
      showProgress: true,
      status: "ready"
    };
  }

  if (sectionKey === "needs_attention" || item.failure_summary || item.processing_status === "failed") {
    return {
      progress: 100,
      showProgress: false,
      status: "needs_attention"
    };
  }

  if (item.processing_status === "pending") {
    return {
      progress: 24,
      showProgress: true,
      status: "analyzing"
    };
  }

  if (item.processing_status === "running") {
    return {
      progress: 68,
      showProgress: true,
      status: "detecting"
    };
  }

  return {
    progress: 92,
    showProgress: true,
    status: "matching"
  };
}

function ProcessingProgressBar({
  initialProgress,
  progress
}: {
  initialProgress?: number;
  progress: number;
}) {
  const animatedWidth = useRef(new Animated.Value(initialProgress ?? progress)).current;

  useEffect(() => {
    Animated.timing(animatedWidth, {
      toValue: progress,
      duration: progress >= 100 ? 260 : 420,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false
    }).start();
  }, [animatedWidth, progress]);

  return (
    <View style={styles.progressTrack}>
      <Animated.View
        style={[
          styles.progressFill,
          {
            width: animatedWidth.interpolate({
              inputRange: [0, 100],
              outputRange: ["0%", "100%"]
            })
          }
        ]}
      />
    </View>
  );
}

export function ProcessingTab({ onOpenItem, readyCount = 0, sections }: ProcessingTabProps) {
  const [completedItems, setCompletedItems] = useState<CompletedProcessingItem[]>([]);
  const previousProcessingRef = useRef<Map<string, ClosetDraftSnapshot>>(new Map());

  const liveEntries = useMemo(
    () =>
      sections.flatMap((section) =>
        section.items.map((item) => ({
          item,
          sectionKey: section.key
        }))
      ),
    [sections]
  );

  const items = useMemo(
    (): ProcessingListItem[] => {
      const liveIds = new Set(liveEntries.map(({ item }) => item.id));
      const transitioning: ProcessingListItem[] = completedItems
        .filter(({ item }) => !liveIds.has(item.id))
        .map(({ item, progressFrom }) => ({
          initialProgress: progressFrom,
          item,
          sectionKey: "processing" as const
        }));

      const live: ProcessingListItem[] = liveEntries.map(({ item, sectionKey }) => ({
        item,
        sectionKey
      }));

      return transitioning.concat(live);
    },
    [completedItems, liveEntries]
  );

  useEffect(() => {
    const liveIds = new Set(liveEntries.map(({ item }) => item.id));
    const nextCompleted: CompletedProcessingItem[] = [];

    for (const [itemId, item] of previousProcessingRef.current.entries()) {
      if (liveIds.has(itemId)) {
        continue;
      }

      nextCompleted.push({
        expiresAt: Date.now() + 700,
        item,
        progressFrom: getVisualState(item, "processing").progress
      });
    }

    if (nextCompleted.length > 0) {
      setCompletedItems((current) => {
        const existingIds = new Set(current.map(({ item }) => item.id));
        return current.concat(nextCompleted.filter(({ item }) => !existingIds.has(item.id)));
      });
    }

    previousProcessingRef.current = new Map(
      liveEntries
        .filter(({ sectionKey }) => sectionKey === "processing")
        .map(({ item }) => [item.id, item])
    );
  }, [liveEntries]);

  useEffect(() => {
    if (completedItems.length === 0) {
      return;
    }

    const timeout = setTimeout(() => {
      setCompletedItems((current) => current.filter(({ expiresAt }) => expiresAt > Date.now()));
    }, 120);

    return () => clearTimeout(timeout);
  }, [completedItems]);

  return (
    <View style={styles.root}>
      <Pressable
        onPress={() => router.push("/add" as Href)}
        style={({ pressed }) => [styles.uploadPrompt, pressed ? styles.pressed : null]}
      >
        <View style={styles.uploadIconWrap}>
          <Feather color={palette.darkText} name="plus" size={20} />
        </View>
        <View style={styles.uploadCopy}>
          <AppText color={palette.darkText} style={styles.uploadTitle}>
            Add more photos
          </AppText>
          <AppText color={palette.warmGray} style={styles.uploadBody}>
            Keep going - I&apos;ll handle the rest
          </AppText>
        </View>
      </Pressable>

      {items.length === 0 ? (
        <View style={styles.emptyState}>
          <AppText color={palette.warmGray} style={styles.emptyTitle}>
            Nothing processing right now
          </AppText>
          <AppText color={palette.warmGray} style={styles.emptyBody}>
            {readyCount > 0
              ? `${readyCount} item${readyCount === 1 ? " is" : "s are"} ready to confirm in your closet.`
              : "Upload a photo to get started"}
          </AppText>
          {readyCount > 0 ? (
            <Pressable
              onPress={() => router.push("/review" as Href)}
              style={({ pressed }) => [styles.readyButton, pressed ? styles.pressed : null]}
            >
              <AppText color={palette.warmWhite} style={styles.readyButtonLabel}>
                Open Confirmation
              </AppText>
            </Pressable>
          ) : null}
        </View>
      ) : (
        <View style={styles.list}>
          {items.map(({ initialProgress, item, sectionKey }) => {
            const imageUrl = getDraftPrimaryImage(item)?.url;
            const visual = getVisualState(item, sectionKey);

            return (
              <View key={item.id} style={styles.card}>
                <Pressable
                  onPress={() => onOpenItem(item.id)}
                  style={({ pressed }) => [styles.cardContent, pressed ? styles.pressed : null]}
                >
                  <View style={styles.thumbnailWrap}>
                    {imageUrl ? (
                      <Image contentFit="cover" source={{ uri: imageUrl }} style={styles.thumbnail} />
                    ) : (
                      <View style={[styles.thumbnail, styles.thumbnailFallback]} />
                    )}
                  </View>

                  <View style={styles.copy}>
                    <AppText color={palette.darkText} numberOfLines={1} style={styles.cardTitle}>
                      {item.title ?? "New upload"}
                    </AppText>
                    <AppText color={palette.warmGray} numberOfLines={2} style={styles.cardStatus}>
                      {item.failure_summary ?? STATUS_LABELS[visual.status]}
                    </AppText>
                    {visual.showProgress ? (
                      <ProcessingProgressBar
                        initialProgress={initialProgress}
                        progress={visual.progress}
                      />
                    ) : null}
                  </View>
                </Pressable>
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    paddingTop: 8,
    gap: 12
  },
  uploadPrompt: {
    borderRadius: 28,
    backgroundColor: palette.warmWhite,
    paddingHorizontal: 24,
    paddingVertical: 20,
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 1,
    shadowRadius: 18,
    elevation: 5
  },
  uploadIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 999,
    backgroundColor: palette.butter,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "rgba(255, 239, 161, 0.25)",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 10,
    elevation: 3
  },
  uploadCopy: {
    flex: 1,
    gap: 2
  },
  uploadTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  uploadBody: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  list: {
    gap: 12
  },
  card: {
    borderRadius: 24,
    backgroundColor: palette.warmWhite,
    padding: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 1,
    shadowRadius: 18,
    elevation: 5
  },
  cardContent: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 16
  },
  thumbnailWrap: {
    flexShrink: 0
  },
  thumbnail: {
    width: 64,
    height: 64,
    borderRadius: 16,
    backgroundColor: palette.cream
  },
  thumbnailFallback: {
    borderWidth: 1,
    borderColor: palette.border
  },
  copy: {
    flex: 1,
    minWidth: 0
  },
  cardTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  cardStatus: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  progressTrack: {
    marginTop: 8,
    height: 4,
    borderRadius: 999,
    backgroundColor: palette.cream,
    overflow: "hidden"
  },
  progressFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: palette.sage
  },
  removeButton: {
    width: 32,
    height: 32,
    borderRadius: 999,
    backgroundColor: palette.cream,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0
  },
  removeButtonDisabled: {
    opacity: 0.8
  },
  emptyState: {
    paddingVertical: 64,
    alignItems: "center",
    justifyContent: "center"
  },
  emptyTitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    textAlign: "center"
  },
  emptyBody: {
    marginTop: 4,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    textAlign: "center"
  },
  readyButton: {
    marginTop: 16,
    minHeight: 44,
    borderRadius: 999,
    backgroundColor: palette.darkText,
    paddingHorizontal: 20,
    alignItems: "center",
    justifyContent: "center"
  },
  readyButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 17
  },
  pressed: {
    opacity: 0.78
  }
});

export default ProcessingTab;
