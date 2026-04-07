import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { useAuth } from "../../../../src/auth/provider";
import { useClosetItemDetail, useClosetSimilarity } from "../../../../src/closet/hooks";
import { humanizeEnum } from "../../../../src/lib/format";
import { fontFamilies } from "../../../../src/theme";
import { AppText, SkeletonBlock } from "../../../../src/ui";

const palette = {
  background: "#FAF9F7",
  surface: "#FFFFFF",
  text: "#0F172A",
  muted: "#94A3B8",
  coral: "#FF6B6B",
  coralSurface: "#FFF1F1",
  shadow: "rgba(15, 23, 42, 0.08)"
} as const;

function getMatchReason(label: string | null | undefined, signalLabel: string | null | undefined) {
  if (signalLabel) {
    return signalLabel;
  }

  if (label === "duplicate") {
    return "Near duplicate";
  }

  return "Similar style";
}

export default function SimilarItemsScreen() {
  const params = useLocalSearchParams<{ itemId: string | string[] }>();
  const itemId = Array.isArray(params.itemId) ? params.itemId[0] : params.itemId;
  const { session } = useAuth();
  const detail = useClosetItemDetail(session?.access_token, itemId);
  const similarity = useClosetSimilarity(session?.access_token, itemId, "similar");

  if (detail.isLoading || similarity.isLoading) {
    return (
      <View style={styles.loadingScreen}>
        <SkeletonBlock height={110} />
        <SkeletonBlock height={260} />
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
  const title =
    detail.detail.metadata_projection.title ??
    detail.detail.metadata_projection.subcategory ??
    "Confirmed item";

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
              Similar Items
            </AppText>
            <AppText color={palette.muted} style={styles.headerSubtitle}>
              To {title}
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
              {title}
            </AppText>
            <AppText color={palette.muted} numberOfLines={1} style={styles.referenceMeta}>
              {[
                detail.detail.metadata_projection.brand,
                detail.detail.metadata_projection.primary_color
                  ? humanizeEnum(detail.detail.metadata_projection.primary_color)
                  : null
              ]
                .filter(Boolean)
                .join(" · ")}
            </AppText>
          </View>
          <Feather color={palette.coral} name="star" size={18} />
        </View>

        <AppText color={palette.muted} style={styles.sectionLabel}>
          {similarity.items.length} similar items found
        </AppText>

        {similarity.items.length === 0 ? (
          <View style={styles.emptyState}>
            <AppText color={palette.text} style={styles.emptyTitle}>
              Nothing similar yet
            </AppText>
            <AppText color={palette.muted} style={styles.emptyBody}>
              {similarity.snapshot?.similarity_status &&
              similarity.snapshot.similarity_status !== "completed"
                ? `Similarity status: ${humanizeEnum(similarity.snapshot.similarity_status)}`
                : "This piece is currently standing on its own."}
            </AppText>
          </View>
        ) : (
          <View style={styles.grid}>
            {similarity.items.map((item) => (
              <Pressable
                key={item.edge_id}
                onPress={() => router.push(`/closet/${item.other_item.item_id}` as Href)}
                style={({ pressed }) => [
                  styles.gridTile,
                  pressed ? styles.pressed : null
                ]}
              >
                <View style={styles.gridCard}>
                  {item.other_item.display_image?.url ?? item.other_item.thumbnail_image?.url ? (
                    <Image
                      contentFit="cover"
                      source={{
                        uri: item.other_item.display_image?.url ?? item.other_item.thumbnail_image?.url ?? undefined
                      }}
                      style={styles.gridImage}
                    />
                  ) : (
                    <View style={[styles.gridImage, styles.imageFallback]} />
                  )}
                  <AppText color={palette.text} numberOfLines={1} style={styles.gridTitle}>
                    {item.other_item.title ?? "Closet item"}
                  </AppText>
                  <View style={styles.reasonPill}>
                    <AppText color={palette.coral} numberOfLines={1} style={styles.reasonLabel}>
                      {getMatchReason(item.label, item.signals[0]?.label)}
                    </AppText>
                  </View>
                </View>
              </Pressable>
            ))}
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
    width: 64,
    height: 80,
    borderRadius: 12,
    backgroundColor: "#F8F8F6"
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: "rgba(15, 23, 42, 0.08)"
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
    marginBottom: 16,
    fontFamily: fontFamilies.sansBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase"
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
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16
  },
  gridTile: {
    width: "47.5%"
  },
  gridCard: {
    borderRadius: 20,
    backgroundColor: palette.surface,
    padding: 12,
    shadowColor: "rgba(15, 23, 42, 0.06)",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 18,
    elevation: 4
  },
  gridImage: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: 14,
    backgroundColor: "#F8F8F6",
    marginBottom: 12
  },
  gridTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 8
  },
  reasonPill: {
    alignSelf: "flex-start",
    borderRadius: 999,
    backgroundColor: palette.coralSurface,
    paddingHorizontal: 8,
    paddingVertical: 4
  },
  reasonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 10,
    lineHeight: 12
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
