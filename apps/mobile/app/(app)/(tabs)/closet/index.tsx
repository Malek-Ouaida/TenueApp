import { Image } from "expo-image";
import { router, type Href } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";

import { useAuth } from "../../../../src/auth/provider";
import { useClosetMetadataOptions, useConfirmedClosetBrowse } from "../../../../src/closet/hooks";
import { buildBrowseMeta, buildClosetFilterSummary } from "../../../../src/closet/status";
import { useDebouncedValue } from "../../../../src/lib/hooks";
import { colors, radius, spacing } from "../../../../src/theme";
import {
  AppText,
  BrandMark,
  Button,
  Card,
  Chip,
  EmptyState,
  ModalSheet,
  Screen,
  SkeletonBlock
} from "../../../../src/ui";

type SortOption = "newest" | "alphabetical" | "category";

const emptyFilters = {
  category: "",
  subcategory: "",
  color: "",
  material: "",
  pattern: ""
};

export default function ClosetBrowseScreen() {
  const { session } = useAuth();
  const metadata = useClosetMetadataOptions(session?.access_token);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortOption>("newest");
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [draftFilters, setDraftFilters] = useState(emptyFilters);
  const [filters, setFilters] = useState(emptyFilters);
  const debouncedQuery = useDebouncedValue(query, 250);
  const closet = useConfirmedClosetBrowse(session?.access_token, {
    query: debouncedQuery,
    ...filters
  });

  const categoryOptions = metadata.data?.categories ?? [];
  const filterSummary = buildClosetFilterSummary(filters);
  const subcategoryOptions =
    categoryOptions.find((category) => category.name === draftFilters.category)?.subcategories ??
    categoryOptions.flatMap((category) => category.subcategories);

  const sortedItems = [...closet.items].sort((left, right) => {
    if (sort === "alphabetical") {
      return (left.title ?? "").localeCompare(right.title ?? "");
    }

    if (sort === "category") {
      const leftKey = `${left.category ?? ""}-${left.subcategory ?? ""}-${left.title ?? ""}`;
      const rightKey = `${right.category ?? ""}-${right.subcategory ?? ""}-${right.title ?? ""}`;
      return leftKey.localeCompare(rightKey);
    }

    return new Date(right.confirmed_at).getTime() - new Date(left.confirmed_at).getTime();
  });

  return (
    <Screen>
      <View style={styles.topRow}>
        <BrandMark variant="wordmark" subtle />
        <Pressable onPress={() => setIsFilterOpen(true)} style={styles.filterButton}>
          <AppText variant="captionStrong">Filter</AppText>
        </Pressable>
      </View>

      <Card tone="soft">
        <AppText color={colors.textSubtle} variant="eyebrow">
          Closet
        </AppText>
        <AppText variant="display">Confirmed wardrobe, uncluttered by draft noise.</AppText>
        <AppText color={colors.textMuted}>
          Processed imagery leads, search stays calm, and only canonical data belongs in this
          browsing surface.
        </AppText>
        <TextInput
          placeholder="Search your closet"
          placeholderTextColor={colors.textSubtle}
          style={styles.searchInput}
          value={query}
          onChangeText={setQuery}
        />
      </Card>

      <View style={styles.controlsRow}>
        {(["newest", "alphabetical", "category"] as SortOption[]).map((option) => {
          const active = sort === option;

          return (
            <Pressable
              key={option}
              onPress={() => setSort(option)}
              style={[styles.controlPill, active ? styles.controlPillActive : null]}
            >
              <AppText color={active ? colors.text : colors.textSubtle} variant="captionStrong">
                {option === "newest"
                  ? "Newest"
                  : option === "alphabetical"
                    ? "A-Z"
                    : "Category"}
              </AppText>
            </Pressable>
          );
        })}
      </View>

      {filterSummary ? (
        <View style={styles.activeFilterRow}>
          <Chip label={filterSummary} tone="organize" />
          <Pressable
            onPress={() => {
              setFilters(emptyFilters);
              setDraftFilters(emptyFilters);
            }}
          >
            <AppText color={colors.text} variant="captionStrong">
              Clear filters
            </AppText>
          </Pressable>
        </View>
      ) : null}

      {closet.isLoading ? (
        <View style={styles.grid}>
          {[0, 1, 2, 3].map((index) => (
            <SkeletonBlock key={index} height={250} style={styles.gridTile} />
          ))}
        </View>
      ) : sortedItems.length === 0 ? (
        <Card tone="soft">
          <EmptyState
            eyebrow="Closet"
            title="Nothing matches this view."
            copy="Try another search, clear the filters, or confirm more items from the review inbox."
          />
        </Card>
      ) : (
        <View style={styles.grid}>
          {sortedItems.map((item) => (
            <Pressable
              key={item.item_id}
              onPress={() => router.push(`/closet/${item.item_id}` as Href)}
              style={styles.gridTile}
            >
              <Card padded={false} shadow={false} style={styles.gridCard} tone="soft">
                {item.display_image?.url ?? item.thumbnail_image?.url ? (
                  <Image
                    source={{ uri: item.display_image?.url ?? item.thumbnail_image?.url ?? undefined }}
                    style={styles.gridImage}
                    contentFit="cover"
                  />
                ) : (
                  <View style={[styles.gridImage, styles.imageFallback]} />
                )}
                <View style={styles.gridBody}>
                  <AppText numberOfLines={2} variant="cardTitle">
                    {item.title ?? "Confirmed item"}
                  </AppText>
                  <AppText color={colors.textMuted} numberOfLines={3} variant="caption">
                    {buildBrowseMeta(item) ?? "Confirmed metadata"}
                  </AppText>
                </View>
              </Card>
            </Pressable>
          ))}
        </View>
      )}

      {closet.nextCursor ? (
        <Button
          label="Load More"
          loading={closet.isLoadingMore}
          onPress={() => void closet.loadMore()}
          variant="secondary"
        />
      ) : null}

      <ModalSheet
        visible={isFilterOpen}
        onClose={() => setIsFilterOpen(false)}
        footer={
          <View style={styles.sheetFooter}>
            <Button
              label="Apply Filters"
              onPress={() => {
                setFilters(draftFilters);
                setIsFilterOpen(false);
              }}
              tone="organize"
            />
            <Button
              label="Reset"
              onPress={() => {
                setDraftFilters(emptyFilters);
                setFilters(emptyFilters);
              }}
              variant="secondary"
            />
          </View>
        }
      >
        <AppText variant="title">Closet filters</AppText>
        <FilterGroup
          title="Category"
          options={categoryOptions.map((option) => option.name)}
          selected={draftFilters.category}
          onSelect={(value) =>
            setDraftFilters((current) => ({
              ...current,
              category: value === current.category ? "" : value,
              subcategory: ""
            }))
          }
        />
        <FilterGroup
          title="Subcategory"
          options={subcategoryOptions}
          selected={draftFilters.subcategory}
          onSelect={(value) =>
            setDraftFilters((current) => ({
              ...current,
              subcategory: value === current.subcategory ? "" : value
            }))
          }
        />
        <FilterGroup
          title="Color"
          options={metadata.data?.colors ?? []}
          selected={draftFilters.color}
          onSelect={(value) =>
            setDraftFilters((current) => ({
              ...current,
              color: value === current.color ? "" : value
            }))
          }
        />
        <FilterGroup
          title="Material"
          options={metadata.data?.materials ?? []}
          selected={draftFilters.material}
          onSelect={(value) =>
            setDraftFilters((current) => ({
              ...current,
              material: value === current.material ? "" : value
            }))
          }
        />
        <FilterGroup
          title="Pattern"
          options={metadata.data?.patterns ?? []}
          selected={draftFilters.pattern}
          onSelect={(value) =>
            setDraftFilters((current) => ({
              ...current,
              pattern: value === current.pattern ? "" : value
            }))
          }
        />
      </ModalSheet>
    </Screen>
  );
}

function FilterGroup({
  title,
  options,
  selected,
  onSelect
}: {
  title: string;
  options: string[];
  selected: string;
  onSelect: (value: string) => void;
}) {
  if (!options.length) {
    return null;
  }

  return (
    <View style={styles.filterGroup}>
      <AppText variant="bodyStrong">{title}</AppText>
      <View style={styles.filterOptions}>
        {options.map((option) => {
          const active = option === selected;

          return (
            <Pressable
              key={option}
              onPress={() => onSelect(option)}
              style={[styles.optionChip, active ? styles.optionChipActive : null]}
            >
              <AppText color={active ? colors.text : colors.textSubtle} variant="captionStrong">
                {option}
              </AppText>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  filterButton: {
    minHeight: 42,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  },
  searchInput: {
    minHeight: 58,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceElevated,
    paddingHorizontal: spacing.md,
    color: colors.text,
    fontFamily: "Manrope_500Medium",
    fontSize: 16
  },
  controlsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  controlPill: {
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  },
  controlPillActive: {
    backgroundColor: colors.cornflowerSurface,
    borderColor: "rgba(174, 197, 241, 0.62)"
  },
  activeFilterRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  gridTile: {
    width: "47%"
  },
  gridCard: {
    gap: spacing.sm
  },
  gridImage: {
    width: "100%",
    height: 184,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    backgroundColor: colors.backgroundMuted
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: colors.border
  },
  gridBody: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    gap: spacing.xs
  },
  sheetFooter: {
    gap: spacing.sm
  },
  filterGroup: {
    gap: spacing.sm
  },
  filterOptions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  optionChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  },
  optionChipActive: {
    backgroundColor: colors.cornflowerSurface,
    borderColor: "rgba(174, 197, 241, 0.62)"
  }
});
