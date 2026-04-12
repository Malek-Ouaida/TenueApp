import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useFocusEffect, type Href } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";

import { useAuth } from "../auth/provider";
import { formatRelativeDate, humanizeEnum } from "../lib/format";
import { useLookbookEntries } from "./hooks";
import { AppText } from "../ui";
import { SecondaryActionButton } from "../ui/feature-components";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";
import type { LookbookEntryFilters, LookbookEntrySummarySnapshot } from "./types";

const LOOKBOOK_TABS = ["All", "Logged", "Recreate", "Inspiration", "Drafts"] as const;

function filtersForTab(tab: (typeof LOOKBOOK_TABS)[number]): LookbookEntryFilters {
  switch (tab) {
    case "Logged":
      return { status: "published", intent: "logged" };
    case "Recreate":
      return { status: "published", intent: "recreate" };
    case "Inspiration":
      return { status: "published", intent: "inspiration" };
    case "Drafts":
      return { status: "draft" };
    default:
      return { status: "published" };
  }
}

function push(href: string) {
  router.push(href as Href);
}

function formatEntryTitle(entry: LookbookEntrySummarySnapshot) {
  if (entry.title) {
    return entry.title;
  }
  if (entry.caption) {
    return entry.caption.length > 36 ? `${entry.caption.slice(0, 33)}...` : entry.caption;
  }
  if (entry.source_kind === "wear_log" && entry.source_snapshot?.context) {
    return humanizeEnum(entry.source_snapshot.context);
  }
  return entry.intent === "logged" ? "Saved daily look" : humanizeEnum(entry.intent);
}

function formatEntryMeta(entry: LookbookEntrySummarySnapshot) {
  const parts = [formatRelativeDate(entry.published_at ?? entry.updated_at)];
  if (entry.linked_item_count > 0) {
    parts.push(`${entry.linked_item_count} items`);
  }
  return parts.join(" · ");
}

function emptyStateCopy(tab: (typeof LOOKBOOK_TABS)[number]) {
  switch (tab) {
    case "Logged":
      return {
        title: "No saved daily looks",
        subtitle: "Save a confirmed wear log to keep the outfits worth repeating."
      };
    case "Recreate":
      return {
        title: "Nothing to recreate yet",
        subtitle: "Add an older photo from your gallery when you want to rebuild a look."
      };
    case "Inspiration":
      return {
        title: "No inspiration saved",
        subtitle: "Pull a photo from your gallery when something is worth keeping in memory."
      };
    case "Drafts":
      return {
        title: "No drafts waiting",
        subtitle: "Draft looks stay here until you are ready to publish them."
      };
    default:
      return {
        title: "Your lookbook is empty",
        subtitle: "Start with a gallery photo or save a confirmed daily log."
      };
  }
}

export default function LookbookScreen() {
  const { session } = useAuth();
  const [activeTab, setActiveTab] = useState<(typeof LOOKBOOK_TABS)[number]>("All");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const lookbook = useLookbookEntries(session?.access_token, filtersForTab(activeTab), 50);
  const empty = emptyStateCopy(activeTab);
  const refreshRef = useRef(lookbook.refresh);

  useEffect(() => {
    refreshRef.current = lookbook.refresh;
  }, [lookbook.refresh]);

  useFocusEffect(
    useCallback(() => {
      void refreshRef.current();
    }, [])
  );

  async function handleRefresh() {
    setIsRefreshing(true);
    try {
      await lookbook.refresh();
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <ScrollView
      bounces={false}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          onRefresh={() => void handleRefresh()}
          refreshing={isRefreshing}
          tintColor={featurePalette.foreground}
        />
      }
      showsVerticalScrollIndicator={false}
      style={styles.screen}
    >
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.headerButton}>
          <Feather color={featurePalette.foreground} name="arrow-left" size={18} />
        </Pressable>
        <Pressable onPress={() => push("/lookbook/add")} style={styles.headerButton}>
          <Feather color={featurePalette.foreground} name="plus" size={18} />
        </Pressable>
      </View>

      <View style={styles.titleBlock}>
        <AppText style={styles.title}>Lookbook</AppText>
        <AppText style={styles.subtitle}>Private looks built from real outfits and photos you want to revisit.</AppText>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.tabs}
      >
        {LOOKBOOK_TABS.map((tab) => (
          <Pressable
            key={tab}
            onPress={() => setActiveTab(tab)}
            style={[
              styles.tab,
              activeTab === tab ? styles.tabActive : null,
              featureShadows.sm
            ]}
          >
            <AppText style={[styles.tabLabel, activeTab === tab ? styles.tabLabelActive : null]}>
              {tab}
            </AppText>
          </Pressable>
        ))}
      </ScrollView>

      {lookbook.error ? (
        <View style={styles.noticeCard}>
          <AppText style={styles.noticeTitle}>Lookbook unavailable</AppText>
          <AppText style={styles.noticeBody}>{lookbook.error}</AppText>
          <View style={styles.noticeAction}>
            <SecondaryActionButton
              label="Try again"
              onPress={() => void handleRefresh()}
              icon={<Feather color={featurePalette.foreground} name="refresh-cw" size={16} />}
            />
          </View>
        </View>
      ) : null}

      {lookbook.isLoading ? (
        <View style={styles.emptyState}>
          <View style={styles.emptyIcon}>
            <Feather color={featurePalette.muted} name="loader" size={24} />
          </View>
          <AppText style={styles.emptyTitle}>Loading looks</AppText>
          <AppText style={styles.emptySubtitle}>Pulling your latest saved looks into the feed.</AppText>
        </View>
      ) : lookbook.items.length > 0 ? (
        <View style={styles.grid}>
          {lookbook.items.map((entry) => (
            <Pressable
              key={entry.id}
              onPress={() => push(`/lookbook/${entry.id}`)}
              style={({ pressed }) => [styles.gridItem, pressed ? styles.pressedWide : null]}
            >
              <View style={styles.gridImageFrame}>
                {entry.primary_image?.url ? (
                  <Image contentFit="cover" source={{ uri: entry.primary_image.url }} style={styles.gridImage} />
                ) : (
                  <View style={styles.gridFallback}>
                    <Feather color={featurePalette.muted} name="image" size={20} />
                  </View>
                )}
                <View style={styles.badgeRow}>
                  <View style={styles.sourceBadge}>
                    <AppText style={styles.sourceBadgeLabel}>
                      {entry.status === "draft" ? "Draft" : humanizeEnum(entry.intent)}
                    </AppText>
                  </View>
                </View>
              </View>
              <AppText numberOfLines={2} style={styles.gridTitle}>
                {formatEntryTitle(entry)}
              </AppText>
              <AppText numberOfLines={2} style={styles.gridMeta}>
                {formatEntryMeta(entry)}
              </AppText>
            </Pressable>
          ))}
        </View>
      ) : (
        <View style={styles.emptyState}>
          <View style={styles.emptyIcon}>
            <Feather color={featurePalette.muted} name="bookmark" size={24} />
          </View>
          <AppText style={styles.emptyTitle}>{empty.title}</AppText>
          <AppText style={styles.emptySubtitle}>{empty.subtitle}</AppText>
        </View>
      )}

      {lookbook.nextCursor ? (
        <View style={styles.loadMore}>
          <SecondaryActionButton
            label={lookbook.isLoadingMore ? "Loading..." : "Load more"}
            onPress={() => void lookbook.loadMore()}
            icon={<Feather color={featurePalette.foreground} name="chevron-down" size={16} />}
          />
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  content: {
    paddingTop: 56,
    paddingBottom: 132
  },
  header: {
    paddingHorizontal: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  headerButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.9)",
    ...featureShadows.sm
  },
  titleBlock: {
    paddingHorizontal: 24,
    marginTop: 12,
    marginBottom: 20
  },
  title: {
    ...featureTypography.display
  },
  subtitle: {
    ...featureTypography.body,
    marginTop: 6
  },
  tabs: {
    paddingHorizontal: 24,
    gap: 8,
    marginBottom: 24
  },
  tab: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: "#FFFFFF"
  },
  tabActive: {
    backgroundColor: featurePalette.foreground
  },
  tabLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.muted
  },
  tabLabelActive: {
    color: "#FFFFFF"
  },
  noticeCard: {
    marginHorizontal: 24,
    marginBottom: 20,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    padding: 16,
    ...featureShadows.sm
  },
  noticeTitle: {
    ...featureTypography.bodyStrong,
    color: featurePalette.foreground
  },
  noticeBody: {
    ...featureTypography.label,
    marginTop: 4
  },
  noticeAction: {
    marginTop: 12
  },
  grid: {
    paddingHorizontal: 24,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12
  },
  gridItem: {
    width: "47%"
  },
  gridImageFrame: {
    aspectRatio: 3 / 4,
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 8,
    position: "relative"
  },
  gridImage: {
    width: "100%",
    height: "100%"
  },
  gridFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  badgeRow: {
    position: "absolute",
    left: 8,
    right: 8,
    top: 8,
    flexDirection: "row",
    justifyContent: "flex-start"
  },
  sourceBadge: {
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.86)",
    paddingHorizontal: 10,
    paddingVertical: 6
  },
  sourceBadgeLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.foreground
  },
  gridTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  gridMeta: {
    ...featureTypography.label,
    marginTop: 4
  },
  emptyState: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 36,
    paddingTop: 84
  },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16
  },
  emptyTitle: {
    ...featureTypography.bodyStrong,
    color: featurePalette.foreground,
    textAlign: "center"
  },
  emptySubtitle: {
    ...featureTypography.label,
    marginTop: 4,
    textAlign: "center"
  },
  loadMore: {
    marginTop: 20,
    paddingHorizontal: 24
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
