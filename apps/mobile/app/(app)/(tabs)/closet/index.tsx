import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useFocusEffect, useLocalSearchParams, type Href } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View
} from "react-native";

import { useAuth } from "../../../../src/auth/provider";
import { ProcessingTab } from "../../../../src/closet/ProcessingTab";
import {
  prefetchClosetReviewItem,
  useReviewQueue,
  useConfirmedClosetBrowse,
  useClosetMetadataOptions
} from "../../../../src/closet/hooks";
import {
  useClosetItemUsageIndex
} from "../../../../src/closet/insights";
import { isReviewableDraft } from "../../../../src/closet/status";
import { useDebouncedValue, usePolling } from "../../../../src/lib/hooks";
import { humanizeEnum } from "../../../../src/lib/format";
import { colors, fontFamilies } from "../../../../src/theme";
import { AppText, EmptyState, ModalSheet, Screen, SkeletonBlock } from "../../../../src/ui";

const palette = {
  cream: "#FAF9F7",
  warmWhite: "#FFFFFF",
  darkText: "#0F172A",
  warmGray: "#64748B",
  muted: "#94A3B8",
  subtle: "#CBD5E1",
  border: "#E2E8F0",
  chipBorder: "#F1F0EE",
  cardShadow: "rgba(15, 23, 42, 0.06)",
  coral: "#FF6B6B",
  coralSurface: "#FFF1F1",
  sageSurface: "#F0FDF4",
  butter: colors.butter,
  lavender: colors.lavender
} as const;

type SortOption = "newest" | "oldest" | "most_worn" | "least_worn" | "recently_worn";

const DEFAULT_CATEGORIES = [
  { id: "all", label: "All" },
  { id: "tops", label: "Tops" },
  { id: "bottoms", label: "Bottoms" },
  { id: "dresses", label: "Dresses" },
  { id: "outerwear", label: "Outerwear" },
  { id: "shoes", label: "Shoes" },
  { id: "bags", label: "Bags" },
  { id: "accessories", label: "Accessories" }
] as const;

const sortLabels: Record<SortOption, string> = {
  newest: "Newest first",
  oldest: "Oldest first",
  most_worn: "Most worn",
  least_worn: "Least worn",
  recently_worn: "Recently worn"
};

function getDaysSince(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const timestamp = new Date(value).getTime();
  return Math.max(0, Math.round((Date.now() - timestamp) / (1000 * 60 * 60 * 24)));
}

function buildItemTag(
  itemId: string,
  confirmedAt: string,
  wearCount: number,
  mostWornItemId: string | null,
  lastWornDate: string | null | undefined
) {
  if (itemId === mostWornItemId && wearCount > 0) {
    return "Most worn";
  }

  const addedDaysAgo = getDaysSince(confirmedAt);
  if (addedDaysAgo != null && addedDaysAgo <= 7) {
    return "Recently added";
  }

  if (wearCount === 0) {
    return "Ready to style";
  }

  const lastWornDaysAgo = getDaysSince(lastWornDate);
  if (lastWornDaysAgo != null && lastWornDaysAgo <= 3) {
    return `Last worn ${lastWornDaysAgo}d ago`;
  }

  return null;
}

function getMaterialOptions(materials: string[]) {
  return ["All", ...materials];
}

function getColorOptions(colorsList: string[]) {
  return ["All", ...colorsList];
}

export default function ClosetBrowseScreen() {
  const params = useLocalSearchParams<{ tab?: string | string[] }>();
  const requestedTab = Array.isArray(params.tab) ? params.tab[0] : params.tab;
  const closetRefreshRef = useRef<() => Promise<void>>(async () => {});
  const reviewRefreshRef = useRef<() => Promise<void>>(async () => {});
  const { session } = useAuth();
  const metadata = useClosetMetadataOptions(session?.access_token);
  const reviewQueue = useReviewQueue(session?.access_token);
  const usageIndex = useClosetItemUsageIndex(session?.access_token);

  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [sortBy, setSortBy] = useState<SortOption>("newest");
  const [draftSortBy, setDraftSortBy] = useState<SortOption>("newest");
  const [appliedColor, setAppliedColor] = useState("All");
  const [draftColor, setDraftColor] = useState("All");
  const [appliedMaterial, setAppliedMaterial] = useState("All");
  const [draftMaterial, setDraftMaterial] = useState("All");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [draftIncludeArchived, setDraftIncludeArchived] = useState(false);
  const [showFilter, setShowFilter] = useState(false);
  const [activeTab, setActiveTab] = useState<"closet" | "processing">(
    requestedTab === "processing" ? "processing" : "closet"
  );

  const debouncedQuery = useDebouncedValue(query, 250);
  const closet = useConfirmedClosetBrowse(
    session?.access_token,
    {
      query: debouncedQuery,
      category: selectedCategory === "all" ? "" : selectedCategory,
      color: appliedColor === "All" ? "" : appliedColor,
      material: appliedMaterial === "All" ? "" : appliedMaterial,
      include_archived: includeArchived
    },
    50
  );

  const categories = useMemo(() => {
    const metadataCategories =
      metadata.data?.categories.map((category) => ({
        id: category.name,
        label: humanizeEnum(category.name)
      })) ?? [];
    const observedCategories = closet.items
      .map((item) => item.category)
      .filter((value): value is string => Boolean(value))
      .filter((value, index, values) => values.indexOf(value) === index)
      .map((value) => ({
        id: value,
        label: humanizeEnum(value)
      }));

    const deduped = [...DEFAULT_CATEGORIES, ...metadataCategories, ...observedCategories].filter(
      (entry, index, entries) => entries.findIndex((candidate) => candidate.id === entry.id) === index
    );

    return deduped;
  }, [closet.items, metadata.data?.categories]);

  const sortedItems = useMemo(() => {
    const usageByItemId = usageIndex.snapshot.byItemId;

    return [...closet.items].sort((left, right) => {
      const leftUsage = usageByItemId[left.item_id];
      const rightUsage = usageByItemId[right.item_id];

      if (sortBy === "oldest") {
        return new Date(left.confirmed_at).getTime() - new Date(right.confirmed_at).getTime();
      }

      if (sortBy === "most_worn") {
        return (rightUsage?.wear_count ?? 0) - (leftUsage?.wear_count ?? 0);
      }

      if (sortBy === "least_worn") {
        return (leftUsage?.wear_count ?? 0) - (rightUsage?.wear_count ?? 0);
      }

      if (sortBy === "recently_worn") {
        return new Date(rightUsage?.last_worn_date ?? 0).getTime() - new Date(leftUsage?.last_worn_date ?? 0).getTime();
      }

      return new Date(right.confirmed_at).getTime() - new Date(left.confirmed_at).getTime();
    });
  }, [closet.items, sortBy, usageIndex.snapshot.byItemId]);

  const needsReviewCount =
    reviewQueue.sections.find((section) => section.key === "needs_review")?.items.length ?? 0;
  const firstReviewableId = reviewQueue.items.find(isReviewableDraft)?.id ?? null;
  const processingSections = reviewQueue.sections.filter((section) => section.key !== "needs_review");
  const processingCount = processingSections.reduce((total, section) => total + section.items.length, 0);
  const hasActiveFilters =
    appliedColor !== "All" || appliedMaterial !== "All" || includeArchived || sortBy !== "newest";
  const colorOptions = getColorOptions(metadata.data?.colors ?? []);
  const materialOptions = getMaterialOptions(metadata.data?.materials ?? []);

  useEffect(() => {
    closetRefreshRef.current = closet.refresh;
  }, [closet.refresh]);

  useEffect(() => {
    reviewRefreshRef.current = reviewQueue.refresh;
  }, [reviewQueue.refresh]);

  usePolling(
    () => reviewRefreshRef.current(),
    activeTab === "processing" || processingCount > 0,
    3000
  );

  useFocusEffect(
    useCallback(() => {
      void reviewRefreshRef.current();
      void closetRefreshRef.current();
    }, [])
  );

  useEffect(() => {
    if (activeTab !== "processing") {
      return;
    }

    void reviewRefreshRef.current();
  }, [activeTab]);

  useEffect(() => {
    setActiveTab(requestedTab === "processing" ? "processing" : "closet");
  }, [requestedTab]);

  useEffect(() => {
    if (
      requestedTab ||
      closet.isLoading ||
      reviewQueue.isLoading ||
      activeTab !== "closet"
    ) {
      return;
    }

    if (sortedItems.length === 0 && processingSections.length > 0 && needsReviewCount === 0) {
      setActiveTab("processing");
    }
  }, [
    activeTab,
    closet.isLoading,
    needsReviewCount,
    processingSections.length,
    requestedTab,
    reviewQueue.isLoading,
    sortedItems.length
  ]);

  return (
    <>
      <Screen
        backgroundColor={palette.cream}
        contentContainerStyle={styles.screenContent}
        padded={false}
      >
        <View style={styles.page}>
          <View style={styles.header}>
            <View>
              <AppText color={palette.darkText} style={styles.headerTitle}>
                Closet
              </AppText>
              <AppText color={palette.warmGray} style={styles.headerSubtitle}>
                Your confirmed wardrobe
              </AppText>
            </View>

            {activeTab === "closet" ? (
              <Pressable
                onPress={() => setShowFilter(true)}
                style={({ pressed }) => [
                  styles.iconButton,
                  pressed ? styles.pressed : null
                ]}
              >
                <Feather color={palette.darkText} name="sliders" size={20} />
                {hasActiveFilters ? <View style={styles.filterDot} /> : null}
              </Pressable>
            ) : (
              <View style={styles.iconGhost} />
            )}
          </View>

          <View style={styles.tabToggleShell}>
            <View style={styles.tabToggle}>
              <Pressable
                onPress={() => setActiveTab("closet")}
                style={({ pressed }) => [
                  styles.tabButton,
                  activeTab === "closet" ? styles.tabButtonActive : null,
                  pressed ? styles.pressed : null
                ]}
              >
                <AppText
                  color={activeTab === "closet" ? colors.white : palette.warmGray}
                  style={activeTab === "closet" ? styles.tabButtonLabelActive : styles.tabButtonLabel}
                >
                  My Closet
                </AppText>
              </Pressable>

              <Pressable
                onPress={() => {
                  setShowFilter(false);
                  setActiveTab("processing");
                }}
                style={({ pressed }) => [
                  styles.tabButton,
                  activeTab === "processing" ? styles.tabButtonActive : null,
                  pressed ? styles.pressed : null
                ]}
              >
                <View style={styles.processingTabButton}>
                  <AppText
                    color={activeTab === "processing" ? colors.white : palette.warmGray}
                    style={activeTab === "processing" ? styles.tabButtonLabelActive : styles.tabButtonLabel}
                  >
                    Processing
                  </AppText>
                  {processingCount > 0 ? (
                    <View
                      style={[
                        styles.processingBadge,
                        activeTab === "processing" ? styles.processingBadgeActive : styles.processingBadgeIdle
                      ]}
                    >
                      <AppText
                        color={palette.darkText}
                        style={styles.processingBadgeLabel}
                      >
                        {processingCount}
                      </AppText>
                    </View>
                  ) : null}
                </View>
              </Pressable>
            </View>
          </View>

          {activeTab === "processing" ? (
            <ProcessingTab
              onOpenItem={(reviewItemId) => router.push(`/review/${reviewItemId}` as Href)}
              readyCount={needsReviewCount}
              sections={processingSections}
            />
          ) : (
            <>
              <View style={styles.searchShell}>
                <Feather color={palette.warmGray} name="search" size={20} />
                <TextInput
                  onChangeText={setQuery}
                  placeholder="Search your closet"
                  placeholderTextColor={palette.warmGray}
                  style={styles.searchInput}
                  value={query}
                />
              </View>

              <ScrollView
                contentContainerStyle={styles.summaryRow}
                horizontal
                showsHorizontalScrollIndicator={false}
              >
                <SummaryPill label={`${sortedItems.length} items`} />
                <SummaryPill label={includeArchived ? "Confirmed + archived" : "Confirmed only"} />
                <SummaryPill label={sortLabels[sortBy]} />
                {includeArchived ? <SummaryPill label="Including archived" /> : null}
              </ScrollView>

              <ScrollView
                contentContainerStyle={styles.categoriesRow}
                horizontal
                showsHorizontalScrollIndicator={false}
              >
                {categories.map((category) => {
                  const active = selectedCategory === category.id;

                  return (
                    <Pressable
                      key={category.id}
                      onPress={() => setSelectedCategory(category.id)}
                      style={({ pressed }) => [
                        styles.categoryChip,
                        active ? styles.categoryChipActive : null,
                        pressed ? styles.pressed : null
                      ]}
                    >
                      <AppText
                        color={palette.darkText}
                        style={active ? styles.categoryLabelActive : styles.categoryLabel}
                      >
                        {category.label}
                      </AppText>
                    </Pressable>
                  );
                })}
              </ScrollView>

              {needsReviewCount > 0 ? (
                <Pressable
                  onPress={() => {
                    if (session?.access_token && firstReviewableId) {
                      void prefetchClosetReviewItem(session.access_token, firstReviewableId);
                      router.push(`/review/${firstReviewableId}` as Href);
                      return;
                    }

                    router.push("/review" as Href);
                  }}
                  style={({ pressed }) => [
                    styles.pendingBanner,
                    pressed ? styles.pressed : null
                  ]}
                >
                  <View style={styles.pendingCopy}>
                    <View style={styles.pendingIcon}>
                      <Feather color={palette.darkText} name="alert-circle" size={18} />
                    </View>
                    <View style={styles.pendingTextStack}>
                      <AppText color={palette.darkText} style={styles.pendingTitle}>
                        {needsReviewCount} items need confirmation
                      </AppText>
                      <AppText color={palette.warmGray} style={styles.pendingBody}>
                        Review before adding to closet
                      </AppText>
                    </View>
                  </View>
                  <Feather color={palette.darkText} name="chevron-right" size={22} />
                </Pressable>
              ) : null}

              {closet.error ? (
                <View style={styles.noticeCard}>
                  <AppText color={palette.darkText} style={styles.noticeTitle}>
                    Closet could not refresh
                  </AppText>
                  <AppText color={palette.warmGray} style={styles.noticeBody}>
                    {closet.error}
                  </AppText>
                </View>
              ) : null}

              {closet.isLoading ? (
                <View style={styles.grid}>
                  {[0, 1, 2, 3].map((index) => (
                    <SkeletonBlock key={index} height={250} style={styles.gridTile} />
                  ))}
                </View>
              ) : sortedItems.length === 0 ? (
                <View style={styles.emptyStateShell}>
                  <EmptyState
                    copy="Try another search or clear the active filters."
                    eyebrow="Closet"
                    title="Nothing matches this view."
                  />
                </View>
              ) : (
                <View style={styles.grid}>
                  {sortedItems.map((item) => {
                    const usage = usageIndex.snapshot.byItemId[item.item_id];
                    const tag = buildItemTag(
                      item.item_id,
                      item.confirmed_at,
                      usage?.wear_count ?? 0,
                      usageIndex.snapshot.mostWornItemId,
                      usage?.last_worn_date
                    );

                    return (
                      <Pressable
                        key={item.item_id}
                        onPress={() =>
                          router.push(
                            includeArchived
                              ? ({ pathname: "/closet/[itemId]", params: { itemId: item.item_id, archived: "1" } } as Href)
                              : (`/closet/${item.item_id}` as Href)
                          )
                        }
                        style={({ pressed }) => [
                          styles.gridTile,
                          pressed ? styles.gridTilePressed : null
                        ]}
                      >
                        <View style={styles.gridCard}>
                          {item.display_image?.url ?? item.thumbnail_image?.url ? (
                            <Image
                              contentFit="cover"
                              source={{ uri: item.display_image?.url ?? item.thumbnail_image?.url ?? undefined }}
                              style={styles.gridImage}
                            />
                          ) : (
                            <View style={[styles.gridImage, styles.imageFallback]} />
                          )}

                          <View style={styles.gridBody}>
                            <AppText color={palette.darkText} numberOfLines={2} style={styles.gridTitle}>
                              {item.title ?? "Confirmed item"}
                            </AppText>
                            <View style={styles.gridMetaRow}>
                              <AppText color={palette.warmGray} numberOfLines={1} style={styles.gridMeta}>
                                {humanizeEnum(item.category ?? "closet_item")}
                              </AppText>
                              {tag ? (
                                <>
                                  <View style={styles.gridMetaDot} />
                                  <View style={styles.tagPill}>
                                    <AppText color={palette.darkText} numberOfLines={1} style={styles.tagLabel}>
                                      {tag}
                                    </AppText>
                                  </View>
                                </>
                              ) : null}
                            </View>
                          </View>
                        </View>
                      </Pressable>
                    );
                  })}
                </View>
              )}
            </>
          )}
        </View>
      </Screen>

      <ModalSheet
        footer={
          <View style={styles.sheetFooter}>
            <Pressable
              onPress={() => {
                setDraftSortBy("newest");
                setDraftColor("All");
                setDraftMaterial("All");
                setDraftIncludeArchived(false);
                setSortBy("newest");
                setAppliedColor("All");
                setAppliedMaterial("All");
                setIncludeArchived(false);
              }}
              style={({ pressed }) => [
                styles.resetButton,
                pressed ? styles.pressed : null
              ]}
            >
              <AppText color={palette.darkText} style={styles.resetButtonLabel}>
                Reset
              </AppText>
            </Pressable>

            <Pressable
              onPress={() => {
                setSortBy(draftSortBy);
                setAppliedColor(draftColor);
                setAppliedMaterial(draftMaterial);
                setIncludeArchived(draftIncludeArchived);
                setShowFilter(false);
              }}
              style={({ pressed }) => [
                styles.applyButton,
                pressed ? styles.pressed : null
              ]}
            >
              <Feather color={colors.white} name="check" size={16} />
              <AppText color={colors.white} style={styles.applyButtonLabel}>
                Apply
              </AppText>
            </Pressable>
          </View>
        }
        onClose={() => {
          setDraftSortBy(sortBy);
          setDraftColor(appliedColor);
          setDraftMaterial(appliedMaterial);
          setDraftIncludeArchived(includeArchived);
          setShowFilter(false);
        }}
        visible={showFilter}
      >
        <View style={styles.sheetHeader}>
          <AppText color={palette.darkText} style={styles.sheetTitle}>
            Filter & Sort
          </AppText>
          <Pressable
            onPress={() => {
              setDraftSortBy(sortBy);
              setDraftColor(appliedColor);
              setDraftMaterial(appliedMaterial);
              setDraftIncludeArchived(includeArchived);
              setShowFilter(false);
            }}
            style={({ pressed }) => [
              styles.sheetClose,
              pressed ? styles.pressed : null
            ]}
          >
            <Feather color={palette.warmGray} name="x" size={16} />
          </Pressable>
        </View>

        <FilterGroup
          options={Object.entries(sortLabels).map(([value, label]) => ({ label, value }))}
          selectedValue={draftSortBy}
          title="Sort by"
          onSelect={(value) => setDraftSortBy(value as SortOption)}
        />

        <FilterGroup
          options={colorOptions.map((option) => ({ label: humanizeEnum(option), value: option }))}
          selectedValue={draftColor}
          title="Color"
          onSelect={setDraftColor}
        />

        <FilterGroup
          options={materialOptions.map((option) => ({ label: humanizeEnum(option), value: option }))}
          selectedValue={draftMaterial}
          title="Material"
          onSelect={setDraftMaterial}
        />

        <FilterGroup
          options={[
            { label: "Confirmed only", value: "confirmed" },
            { label: "Include archived", value: "include_archived" }
          ]}
          selectedValue={draftIncludeArchived ? "include_archived" : "confirmed"}
          title="Visibility"
          onSelect={(value) => setDraftIncludeArchived(value === "include_archived")}
        />
      </ModalSheet>
    </>
  );
}

function SummaryPill({ label }: { label: string }) {
  return (
    <View style={styles.summaryPill}>
      <AppText color={palette.warmGray} style={styles.summaryLabel}>
        {label}
      </AppText>
    </View>
  );
}

function FilterGroup({
  options,
  onSelect,
  selectedValue,
  title
}: {
  options: Array<{ label: string; value: string }>;
  onSelect: (value: string) => void;
  selectedValue: string;
  title: string;
}) {
  return (
    <View style={styles.filterGroup}>
      <AppText color={palette.muted} style={styles.filterTitle}>
        {title}
      </AppText>
      <View style={styles.filterChipRow}>
        {options.map((option) => {
          const active = option.value === selectedValue;

          return (
            <Pressable
              key={option.value}
              onPress={() => onSelect(option.value)}
              style={({ pressed }) => [
                styles.filterChip,
                active ? styles.filterChipActive : null,
                pressed ? styles.pressed : null
              ]}
            >
              <AppText
                color={active ? colors.white : palette.darkText}
                style={styles.filterChipLabel}
              >
                {option.label}
              </AppText>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screenContent: {
    flexGrow: 1,
    paddingBottom: 132
  },
  page: {
    paddingHorizontal: 24,
    paddingTop: 18,
    gap: 20
  },
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between"
  },
  headerTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 40,
    lineHeight: 42,
    letterSpacing: -1.2
  },
  headerSubtitle: {
    marginTop: 4,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20
  },
  iconButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: palette.warmWhite,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: palette.cardShadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 12,
    elevation: 4
  },
  iconGhost: {
    width: 44,
    height: 44
  },
  filterDot: {
    position: "absolute",
    top: -1,
    right: -1,
    width: 10,
    height: 10,
    borderRadius: 999,
    backgroundColor: palette.coral
  },
  tabToggleShell: {
    marginTop: -2
  },
  tabToggle: {
    borderRadius: 20,
    backgroundColor: palette.warmWhite,
    padding: 4,
    flexDirection: "row",
    shadowColor: palette.cardShadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 12,
    elevation: 3
  },
  tabButton: {
    flex: 1,
    minHeight: 42,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 12
  },
  tabButtonActive: {
    backgroundColor: "#1F2937",
    shadowColor: "rgba(15, 23, 42, 0.15)",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 8,
    elevation: 3
  },
  tabButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 16
  },
  tabButtonLabelActive: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 16
  },
  processingTabButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6
  },
  processingBadge: {
    width: 20,
    height: 20,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center"
  },
  processingBadgeActive: {
    backgroundColor: palette.butter
  },
  processingBadgeIdle: {
    backgroundColor: palette.coral
  },
  processingBadgeLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 10,
    lineHeight: 12
  },
  searchShell: {
    minHeight: 56,
    borderRadius: 28,
    backgroundColor: palette.warmWhite,
    paddingHorizontal: 20,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    shadowColor: palette.cardShadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 12,
    elevation: 3
  },
  searchInput: {
    flex: 1,
    color: palette.darkText,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    paddingVertical: 0
  },
  summaryRow: {
    gap: 8,
    paddingRight: 20
  },
  summaryPill: {
    borderRadius: 20,
    backgroundColor: palette.warmWhite,
    paddingHorizontal: 14,
    paddingVertical: 8
  },
  summaryLabel: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  categoriesRow: {
    gap: 10,
    paddingRight: 20
  },
  categoryChip: {
    borderRadius: 999,
    backgroundColor: palette.warmWhite,
    paddingHorizontal: 20,
    paddingVertical: 12,
    shadowColor: "rgba(15, 23, 42, 0.05)",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 10,
    elevation: 2
  },
  categoryChipActive: {
    backgroundColor: palette.butter
  },
  categoryLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  categoryLabelActive: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 14,
    lineHeight: 18
  },
  pendingBanner: {
    borderRadius: 28,
    backgroundColor: "#FFD2C2",
    paddingHorizontal: 24,
    paddingVertical: 18,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    shadowColor: "rgba(255, 107, 107, 0.22)",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 16,
    elevation: 4
  },
  pendingCopy: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    flex: 1
  },
  pendingIcon: {
    width: 40,
    height: 40,
    borderRadius: 999,
    backgroundColor: palette.warmWhite,
    alignItems: "center",
    justifyContent: "center"
  },
  pendingTextStack: {
    flex: 1,
    gap: 2
  },
  pendingTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 16,
    lineHeight: 20
  },
  pendingBody: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 17
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16
  },
  gridTile: {
    width: "47.5%"
  },
  gridTilePressed: {
    opacity: 0.88,
    transform: [{ scale: 0.985 }]
  },
  gridCard: {
    borderRadius: 28,
    backgroundColor: palette.warmWhite,
    padding: 12,
    shadowColor: "rgba(15, 23, 42, 0.07)",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 1,
    shadowRadius: 20,
    elevation: 5
  },
  gridImage: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: 20,
    backgroundColor: palette.cream
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: palette.border
  },
  gridBody: {
    marginTop: 12,
    gap: 6
  },
  gridTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  gridMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 6
  },
  gridMeta: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 11,
    lineHeight: 15
  },
  gridMetaDot: {
    width: 3,
    height: 3,
    borderRadius: 999,
    backgroundColor: palette.warmGray
  },
  tagPill: {
    borderRadius: 12,
    backgroundColor: palette.lavender,
    paddingHorizontal: 8,
    paddingVertical: 2
  },
  tagLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 9,
    lineHeight: 12
  },
  emptyStateShell: {
    borderRadius: 28,
    backgroundColor: palette.warmWhite,
    paddingHorizontal: 20,
    paddingVertical: 28
  },
  noticeCard: {
    borderRadius: 20,
    backgroundColor: palette.warmWhite,
    padding: 16,
    gap: 4,
    shadowColor: palette.cardShadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 12,
    elevation: 3
  },
  noticeTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  noticeBody: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  sheetHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  sheetTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 20,
    lineHeight: 24
  },
  sheetClose: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#F1F0EE",
    alignItems: "center",
    justifyContent: "center"
  },
  filterGroup: {
    gap: 12
  },
  filterTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase"
  },
  filterChipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  filterChip: {
    borderRadius: 999,
    backgroundColor: palette.cream,
    paddingHorizontal: 14,
    paddingVertical: 10
  },
  filterChipActive: {
    backgroundColor: palette.darkText
  },
  filterChipLabel: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 17
  },
  sheetFooter: {
    gap: 12
  },
  applyButton: {
    minHeight: 48,
    borderRadius: 18,
    backgroundColor: palette.darkText,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  applyButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  resetButton: {
    minHeight: 48,
    borderRadius: 18,
    backgroundColor: palette.cream,
    alignItems: "center",
    justifyContent: "center"
  },
  resetButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  pressed: {
    opacity: 0.78
  }
});
