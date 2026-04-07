import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams } from "expo-router";
import { ScrollView, Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../../../src/auth/provider";
import { useClosetItemDetail, useClosetItemHistory } from "../../../../src/closet/hooks";
import { useClosetItemUsageIndex } from "../../../../src/closet/insights";
import { formatDateTime, humanizeEnum } from "../../../../src/lib/format";
import { fontFamilies } from "../../../../src/theme";
import { AppText, SkeletonBlock } from "../../../../src/ui";

const palette = {
  background: "#FAF9F7",
  surface: "#FFFFFF",
  text: "#0F172A",
  muted: "#94A3B8",
  warmGray: "#64748B",
  line: "#E2E8F0",
  successSurface: "#ECFDF5",
  warningSurface: "#FFFBEB",
  coralSurface: "#FFF1F1",
  infoSurface: "#EEF5FF",
  success: "#10B981",
  warning: "#F59E0B",
  coral: "#FF6B6B",
  info: "#4F7FD8",
  destructive: "#B05246",
  shadow: "rgba(15, 23, 42, 0.08)"
} as const;

function buildEventCopy(eventType: string, payload: unknown) {
  const data = typeof payload === "object" && payload ? (payload as Record<string, unknown>) : null;
  const fieldName =
    typeof data?.field_name === "string" ? humanizeEnum(data.field_name) : null;

  switch (eventType) {
    case "item_created":
      return "Draft created";
    case "upload_finalized":
      return "Image uploaded";
    case "item_confirmed":
      return "Added to closet";
    case "item_archived":
      return "Item archived";
    case "primary_image_set":
      return "Primary image updated";
    case "field_state_user_confirmed":
      return fieldName ? `${fieldName} confirmed` : "Field confirmed";
    case "field_state_user_edited":
      return fieldName ? `${fieldName} edited` : "Details updated";
    case "field_state_user_cleared":
      return fieldName ? `${fieldName} cleared` : "Field cleared";
    case "field_state_user_marked_not_applicable":
      return fieldName ? `${fieldName} marked not applicable` : "Field skipped";
    case "metadata_extraction_completed":
      return "AI suggestions generated";
    case "metadata_extraction_completed_with_issues":
      return "AI suggestions completed with issues";
    case "metadata_normalization_started":
      return "Metadata normalization started";
    case "metadata_normalization_failed":
      return "Metadata normalization failed";
    case "similarity_recompute_completed":
      return "Similarity recomputed";
    case "similarity_edge_marked_duplicate":
      return "Marked duplicate";
    case "similarity_edge_dismissed":
      return "Similarity dismissed";
    default:
      return humanizeEnum(eventType);
  }
}

function getEventTone(eventType: string) {
  if (eventType.includes("archived") || eventType.includes("failed")) {
    return {
      backgroundColor: palette.coralSurface,
      color: palette.destructive,
      icon: "alert-circle" as const
    };
  }

  if (
    eventType.includes("edited") ||
    eventType.includes("cleared") ||
    eventType.includes("confirmed")
  ) {
    return {
      backgroundColor: palette.warningSurface,
      color: palette.warning,
      icon: "edit-3" as const
    };
  }

  if (eventType.includes("similarity")) {
    return {
      backgroundColor: palette.infoSurface,
      color: palette.info,
      icon: "star" as const
    };
  }

  return {
    backgroundColor: palette.successSurface,
    color: palette.success,
    icon: "plus" as const
  };
}

export default function ClosetHistoryScreen() {
  const params = useLocalSearchParams<{ itemId: string | string[] }>();
  const itemId = Array.isArray(params.itemId) ? params.itemId[0] : params.itemId;
  const { session } = useAuth();
  const detail = useClosetItemDetail(session?.access_token, itemId);
  const history = useClosetItemHistory(session?.access_token, itemId);
  const usageIndex = useClosetItemUsageIndex(session?.access_token);

  if (detail.isLoading || history.isLoading) {
    return (
      <View style={styles.loadingScreen}>
        <SkeletonBlock height={110} />
        <SkeletonBlock height={320} />
      </View>
    );
  }

  if (!detail.detail) {
    return (
      <View style={styles.loadingScreen}>
        <AppText color={palette.muted} style={styles.emptyCopy}>
          Item not found
        </AppText>
      </View>
    );
  }

  const itemImage =
    detail.detail.display_image?.url ??
    detail.detail.thumbnail_image?.url ??
    detail.detail.original_image?.url;
  const itemTitle =
    detail.detail.metadata_projection.title ??
    detail.detail.metadata_projection.subcategory ??
    "Confirmed item";
  const usage = itemId ? usageIndex.snapshot.byItemId[itemId] : null;

  return (
    <View style={styles.screen}>
      <ScrollView
        bounces={false}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <Pressable
            onPress={() => router.back()}
            style={({ pressed }) => [styles.backButton, pressed ? styles.pressed : null]}
          >
            <Feather color={palette.text} name="arrow-left" size={18} />
          </Pressable>
          <View style={styles.headerCopy}>
            <AppText color={palette.text} style={styles.headerTitle}>
              History
            </AppText>
            <AppText color={palette.muted} style={styles.headerSubtitle}>
              {itemTitle}
            </AppText>
          </View>
        </View>

        <View style={styles.referenceCard}>
          {itemImage ? (
            <Image contentFit="cover" source={{ uri: itemImage }} style={styles.referenceImage} />
          ) : (
            <View style={[styles.referenceImage, styles.imageFallback]} />
          )}

          <View style={styles.referenceCopy}>
            <AppText color={palette.text} numberOfLines={1} style={styles.referenceTitle}>
              {itemTitle}
            </AppText>
            <AppText color={palette.muted} style={styles.referenceMeta}>
              Added {formatDateTime(detail.detail.confirmed_at ?? detail.detail.created_at)}
            </AppText>
            <AppText color={palette.muted} style={styles.referenceMeta}>
              Worn {usage?.wear_count ?? 0}×
            </AppText>
          </View>

          <MaterialCommunityIcons color={palette.muted} name="eye-outline" size={20} />
        </View>

        <AppText color={palette.muted} style={styles.sectionLabel}>
          Activity
        </AppText>

        {history.items.length === 0 ? (
          <View style={styles.emptyState}>
            <AppText color={palette.text} style={styles.emptyTitle}>
              No history yet
            </AppText>
            <AppText color={palette.muted} style={styles.emptyBody}>
              This item has not accumulated any audit trail events yet.
            </AppText>
          </View>
        ) : (
          <View style={styles.timelineShell}>
            <View style={styles.timelineLine} />
            {history.items.map((event, index) => {
              const tone = getEventTone(event.event_type);

              return (
                <View key={event.id} style={styles.timelineRow}>
                  <View style={[styles.timelineDot, { backgroundColor: tone.backgroundColor }]}>
                    <Feather color={tone.color} name={tone.icon} size={14} />
                  </View>

                  <View style={styles.timelineCopy}>
                    <AppText color={palette.text} style={styles.timelineTitle}>
                      {buildEventCopy(event.event_type, event.payload)}
                    </AppText>
                    <AppText color={palette.muted} style={styles.timelineDate}>
                      {formatDateTime(event.created_at)}
                    </AppText>
                  </View>

                  {index < history.items.length - 1 ? <View style={styles.timelineSpacer} /> : null}
                </View>
              );
            })}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: palette.background
  },
  loadingScreen: {
    flex: 1,
    backgroundColor: palette.background,
    paddingHorizontal: 24,
    paddingTop: 24,
    gap: 20
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 18,
    paddingBottom: 40
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    marginBottom: 20
  },
  backButton: {
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
    fontSize: 18,
    lineHeight: 22
  },
  headerSubtitle: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  referenceCard: {
    borderRadius: 18,
    backgroundColor: palette.surface,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 18,
    elevation: 5
  },
  referenceImage: {
    width: 56,
    height: 70,
    borderRadius: 12,
    backgroundColor: "#F8F8F6"
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: palette.line
  },
  referenceCopy: {
    flex: 1,
    gap: 2
  },
  referenceTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  referenceMeta: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  sectionLabel: {
    marginTop: 20,
    marginBottom: 18,
    fontFamily: fontFamilies.sansBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase"
  },
  timelineShell: {
    position: "relative"
  },
  timelineLine: {
    position: "absolute",
    left: 14,
    top: 4,
    bottom: 4,
    width: 2,
    borderRadius: 999,
    backgroundColor: palette.line
  },
  timelineRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 16,
    paddingBottom: 24,
    position: "relative"
  },
  timelineDot: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1
  },
  timelineCopy: {
    flex: 1,
    paddingTop: 2
  },
  timelineTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  timelineDate: {
    marginTop: 4,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  timelineSpacer: {
    height: 0
  },
  emptyState: {
    paddingVertical: 64,
    alignItems: "center"
  },
  emptyTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  emptyBody: {
    marginTop: 6,
    textAlign: "center",
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
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
