import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useFocusEffect, useLocalSearchParams, type Href } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  PanResponder,
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useConfirmedClosetBrowse, useClosetItemDetail } from "../../../src/closet/hooks";
import { useClosetItemUsageIndex } from "../../../src/closet/insights";
import { compactList, humanizeEnum } from "../../../src/lib/format";
import {
  triggerErrorHaptic,
  triggerSelectionHaptic,
  triggerSuccessHaptic
} from "../../../src/lib/haptics";
import { colors, fontFamilies } from "../../../src/theme";
import { AppText, ModalSheet, SkeletonBlock } from "../../../src/ui";

const palette = {
  background: "#FAF9F7",
  surface: "#FFFFFF",
  darkText: "#0F172A",
  muted: "#94A3B8",
  warmGray: "#64748B",
  border: "#E2E8F0",
  secondary: "#F8F8F6",
  destructive: "#B05246",
  shadow: "rgba(15, 23, 42, 0.08)"
} as const;

function getDaysSince(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  return Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / (1000 * 60 * 60 * 24)));
}

function formatDaysAgo(value: string | null | undefined) {
  const days = getDaysSince(value);
  if (days == null) {
    return "Unknown";
  }
  if (days === 0) {
    return "Today";
  }
  if (days === 1) {
    return "Yesterday";
  }
  if (days < 7) {
    return `${days} days ago`;
  }
  if (days < 30) {
    return `${Math.floor(days / 7)} weeks ago`;
  }
  return `${Math.floor(days / 30)} months ago`;
}

function buildFieldRows(detail: NonNullable<ReturnType<typeof useClosetItemDetail>["detail"]>) {
  const projection = detail.metadata_projection;

  return [
    { label: "Category", value: projection.category ? humanizeEnum(projection.category) : null },
    { label: "Type", value: projection.subcategory ? humanizeEnum(projection.subcategory) : null },
    { label: "Color", value: projection.primary_color ? humanizeEnum(projection.primary_color) : null },
    {
      label: "Additional Colors",
      value: compactList(projection.secondary_colors?.map(humanizeEnum) ?? null)
    },
    { label: "Material", value: projection.material ? humanizeEnum(projection.material) : null },
    { label: "Pattern", value: projection.pattern ? humanizeEnum(projection.pattern) : null },
    { label: "Season", value: compactList(projection.season_tags?.map(humanizeEnum) ?? null) },
    { label: "Occasion", value: compactList(projection.occasion_tags?.map(humanizeEnum) ?? null) },
    { label: "Style", value: compactList(projection.style_tags?.map(humanizeEnum) ?? null) },
    { label: "Fit", value: compactList(projection.fit_tags?.map(humanizeEnum) ?? null) },
    { label: "Silhouette", value: projection.silhouette ? humanizeEnum(projection.silhouette) : null },
    { label: "Attributes", value: compactList(projection.attributes?.map(humanizeEnum) ?? null) },
    { label: "Brand", value: projection.brand ?? null }
  ].filter((field): field is { label: string; value: string } => Boolean(field.value));
}

export default function ClosetItemDetailScreen() {
  const params = useLocalSearchParams<{ itemId: string | string[]; archived?: string | string[] }>();
  const itemId = Array.isArray(params.itemId) ? params.itemId[0] : params.itemId;
  const archivedParam = Array.isArray(params.archived) ? params.archived[0] : params.archived;
  const includeArchived = archivedParam === "1";
  const { session } = useAuth();
  const browse = useConfirmedClosetBrowse(session?.access_token, { include_archived: includeArchived }, 50);
  const detail = useClosetItemDetail(session?.access_token, itemId, { includeArchived });
  const usageIndex = useClosetItemUsageIndex(session?.access_token);
  const [menuOpen, setMenuOpen] = useState(false);
  const [selectedField, setSelectedField] = useState<{ label: string; value: string } | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [offsetX, setOffsetX] = useState(0);

  const orderedItems = browse.items;
  const currentIndex = Math.max(
    0,
    orderedItems.findIndex((item) => item.item_id === itemId)
  );
  const previousItem = currentIndex > 0 ? orderedItems[currentIndex - 1] : null;
  const nextItem = currentIndex < orderedItems.length - 1 ? orderedItems[currentIndex + 1] : null;
  const usage = itemId ? usageIndex.snapshot.byItemId[itemId] : null;

  useFocusEffect(
    useCallback(() => {
      void detail.refresh();
    }, [detail.refresh])
  );

  useEffect(() => {
    const preferredAssetId =
      detail.detail?.original_images.find((image) => image.is_primary)?.asset_id ??
      detail.detail?.original_images[0]?.asset_id ??
      null;
    if (!detail.detail || selectedAssetId === preferredAssetId) {
      return;
    }

    if (selectedAssetId && detail.detail.original_images.some((image) => image.asset_id === selectedAssetId)) {
      return;
    }

    setSelectedAssetId(preferredAssetId);
  }, [detail.detail, selectedAssetId]);

  function buildItemHref(targetItemId: string) {
    return includeArchived
      ? ({ pathname: "/closet/[itemId]", params: { itemId: targetItemId, archived: "1" } } as Href)
      : (`/closet/${targetItemId}` as Href);
  }

  async function archiveItem() {
    const archived = await detail.archive();
    if (archived) {
      await triggerSuccessHaptic();
      router.replace("/closet" as Href);
      return;
    }

    await triggerErrorHaptic();
    setActionMessage(detail.error ?? "Archive failed.");
  }

  async function restoreItem() {
    const restored = await detail.restore();
    if (restored) {
      await triggerSuccessHaptic();
      router.replace(`/closet/${itemId}` as Href);
      return;
    }

    await triggerErrorHaptic();
    setActionMessage(detail.error ?? "Restore failed.");
  }

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, gesture) =>
          !menuOpen &&
          !selectedField &&
          Math.abs(gesture.dx) > 8 &&
          Math.abs(gesture.dx) > Math.abs(gesture.dy),
        onPanResponderMove: (_, gesture) => {
          let nextOffset = gesture.dx;

          if (gesture.dx > 0 && !previousItem) {
            nextOffset *= 0.35;
          }
          if (gesture.dx < 0 && !nextItem) {
            nextOffset *= 0.35;
          }

          setOffsetX(nextOffset);
        },
        onPanResponderRelease: async (_, gesture) => {
          const threshold = 64;

          if (gesture.dx < -threshold && nextItem) {
            await triggerSelectionHaptic();
            router.replace(buildItemHref(nextItem.item_id));
          } else if (gesture.dx > threshold && previousItem) {
            await triggerSelectionHaptic();
            router.replace(buildItemHref(previousItem.item_id));
          }

          setOffsetX(0);
        },
        onPanResponderTerminate: () => {
          setOffsetX(0);
        }
      }),
    [menuOpen, nextItem, previousItem, selectedField]
  );

  if (detail.isLoading) {
    return (
      <View style={styles.loadingScreen}>
        <SkeletonBlock height={360} />
        <SkeletonBlock height={120} />
        <SkeletonBlock height={200} />
      </View>
    );
  }

  if (!detail.detail) {
    return (
      <View style={styles.loadingScreen}>
        <View style={styles.emptyStateCard}>
          <AppText color={palette.darkText} style={styles.emptyTitle}>
            Closet item unavailable
          </AppText>
          <AppText color={palette.warmGray} style={styles.emptyCopy}>
            {detail.error ?? "The confirmed item could not be loaded."}
          </AppText>
          <View style={styles.emptyActions}>
            <Pressable
              onPress={() => router.back()}
              style={({ pressed }) => [styles.emptyActionButton, pressed ? styles.pressed : null]}
            >
              <AppText color={palette.darkText} style={styles.emptyActionLabel}>
                Back
              </AppText>
            </Pressable>
            <Pressable
              onPress={() => void detail.refresh()}
              style={({ pressed }) => [
                styles.emptyActionButton,
                styles.emptyActionButtonPrimary,
                pressed ? styles.pressed : null
              ]}
            >
              <AppText style={styles.emptyActionLabelPrimary}>Retry</AppText>
            </Pressable>
          </View>
        </View>
      </View>
    );
  }

  const selectedOriginalImage =
    detail.detail.original_images.find((image) => image.asset_id === selectedAssetId) ?? null;
  const heroImage =
    selectedOriginalImage?.url ??
    detail.detail.display_image?.url ??
    detail.detail.thumbnail_image?.url ??
    detail.detail.original_image?.url;
  const fields = buildFieldRows(detail.detail);
  const title =
    detail.detail.metadata_projection.title ??
    detail.detail.metadata_projection.subcategory ??
    "Confirmed item";
  const metaLine = [
    `Added ${formatDaysAgo(detail.detail.confirmed_at ?? detail.detail.created_at)}`,
    detail.detail.metadata_projection.brand
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <View style={styles.screen}>
        <View style={styles.floatingHeader}>
          <Pressable
            onPress={() => router.back()}
            style={({ pressed }) => [styles.floatingButton, pressed ? styles.pressed : null]}
          >
            <Feather color={palette.darkText} name="arrow-left" size={20} />
          </Pressable>

          <AppText color={palette.warmGray} style={styles.counterLabel}>
            {orderedItems.length ? `${currentIndex + 1} of ${orderedItems.length}` : "Item"}
          </AppText>

          <Pressable
            onPress={() => setMenuOpen(true)}
            style={({ pressed }) => [styles.floatingButton, pressed ? styles.pressed : null]}
          >
            <Feather color={palette.darkText} name="more-horizontal" size={20} />
          </Pressable>
        </View>

        <ScrollView
          bounces={false}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.heroWrap} {...panResponder.panHandlers}>
            <View style={[styles.heroCard, { transform: [{ translateX: offsetX }] }]}>
              {heroImage ? (
                <Image contentFit="cover" source={{ uri: heroImage }} style={styles.heroImage} />
              ) : (
                <View style={[styles.heroImage, styles.imageFallback]} />
              )}
            </View>
          </View>

          {orderedItems.length > 1 ? (
            <View style={styles.paginationRow}>
              {orderedItems
                .slice(Math.max(0, currentIndex - 3), Math.min(orderedItems.length, currentIndex + 4))
                .map((item) => {
                  const active = item.item_id === itemId;

                  return <View key={item.item_id} style={active ? styles.paginationActive : styles.paginationDot} />;
                })}
            </View>
          ) : null}

          <View style={styles.metaSection}>
            <AppText color={palette.darkText} style={styles.title}>
              {title}
            </AppText>
            <AppText color={palette.warmGray} style={styles.metaLine}>
              {metaLine}
            </AppText>
          </View>

          {detail.detail.lifecycle_status === "archived" ? (
            <View style={styles.statusCard}>
              <AppText color={palette.darkText} style={styles.statusTitle}>
                Archived item
              </AppText>
              <AppText color={palette.warmGray} style={styles.statusBody}>
                This item is hidden from the default closet view until you restore it.
              </AppText>
            </View>
          ) : ["pending", "running", "completed_with_issues"].includes(detail.detail.processing_status) ? (
            <View style={styles.statusCard}>
              <AppText color={palette.darkText} style={styles.statusTitle}>
                Media refresh in progress
              </AppText>
              <AppText color={palette.warmGray} style={styles.statusBody}>
                Tenue is updating processed imagery and metadata after the latest media change.
              </AppText>
            </View>
          ) : null}

          {detail.detail.original_images.length > 1 ? (
            <ScrollView
              horizontal
              contentContainerStyle={styles.imageStrip}
              showsHorizontalScrollIndicator={false}
            >
              {detail.detail.original_images.map((image) => {
                const active = image.asset_id === selectedAssetId;

                return (
                  <Pressable
                    key={image.asset_id}
                    onPress={() => setSelectedAssetId(image.asset_id)}
                    style={({ pressed }) => [
                      styles.imageThumbShell,
                      active ? styles.imageThumbShellActive : null,
                      pressed ? styles.pressed : null
                    ]}
                  >
                    <Image contentFit="cover" source={{ uri: image.url }} style={styles.imageThumb} />
                  </Pressable>
                );
              })}
            </ScrollView>
          ) : null}

          <SectionLabel label="Details" />
          <View style={styles.sectionCard}>
            {fields.map((field, index) => (
              <Pressable
                key={field.label}
                onPress={() => setSelectedField(field)}
                style={({ pressed }) => [styles.detailRow, pressed ? styles.pressed : null]}
              >
                <AppText color={palette.muted} style={styles.detailLabel}>
                  {field.label}
                </AppText>
                <View style={styles.detailValueRow}>
                  <AppText color={palette.darkText} style={styles.detailValue}>
                    {field.value}
                  </AppText>
                  <Feather color={palette.muted} name="chevron-right" size={16} />
                </View>
                {index < fields.length - 1 ? <View style={styles.divider} /> : null}
              </Pressable>
            ))}
          </View>

          <SectionLabel label="Usage" />
          <View style={styles.sectionCard}>
            {usage ? (
              <>
                <View style={styles.usageRow}>
                  <View style={styles.usageBlock}>
                    <AppText color={palette.darkText} style={styles.usageCount}>
                      {usage.wear_count}
                    </AppText>
                    <AppText color={palette.warmGray} style={styles.usageCaption}>
                      times worn
                    </AppText>
                  </View>
                  <View style={styles.usageDivider} />
                  <View style={styles.usageBlock}>
                    <AppText color={palette.darkText} style={styles.usageValue}>
                      {formatDaysAgo(usage.last_worn_date)}
                    </AppText>
                    <AppText color={palette.warmGray} style={styles.usageCaption}>
                      last worn
                    </AppText>
                  </View>
                </View>

                <View style={styles.frequencyShell}>
                  <AppText color={palette.muted} style={styles.frequencyLabel}>
                    Frequency
                  </AppText>
                  <View style={styles.frequencyRow}>
                    {Array.from({ length: 12 }).map((_, index) => {
                      const active = index < Math.min(12, Math.round(usage.wear_count / 3));

                      return (
                        <View
                          key={index}
                          style={[
                            styles.frequencyBar,
                            active ? styles.frequencyBarActive : null
                          ]}
                        />
                      );
                    })}
                  </View>
                </View>
              </>
            ) : (
              <View style={styles.usageEmpty}>
                <AppText color={palette.darkText} style={styles.usageValue}>
                  Not worn yet
                </AppText>
                <AppText color={palette.warmGray} style={styles.usageCaption}>
                  This item will start building history once it appears in wear logs.
                </AppText>
              </View>
            )}
          </View>

          {detail.detail.lifecycle_status !== "archived" ? (
            <View style={styles.quickLinkRow}>
              <Pressable
                onPress={() => router.push(`/closet/${itemId}/similar` as Href)}
                style={({ pressed }) => [styles.quickLinkButton, pressed ? styles.pressed : null]}
              >
                <AppText color={palette.darkText} style={styles.quickLinkLabel}>
                  Similar Items
                </AppText>
              </Pressable>
              <Pressable
                onPress={() => router.push(`/closet/${itemId}/history` as Href)}
                style={({ pressed }) => [styles.quickLinkButton, pressed ? styles.pressed : null]}
              >
                <AppText color={palette.darkText} style={styles.quickLinkLabel}>
                  History
                </AppText>
              </Pressable>
            </View>
          ) : null}

          <View style={styles.actions}>
            {detail.detail.lifecycle_status === "archived" ? (
              <Pressable
                onPress={() => void restoreItem()}
                style={({ pressed }) => [styles.primaryAction, pressed ? styles.pressed : null]}
              >
                <Feather color={colors.white} name="refresh-ccw" size={18} />
                <AppText color={colors.white} style={styles.primaryActionLabel}>
                  {detail.isRestoring ? "Restoring..." : "Restore Item"}
                </AppText>
              </Pressable>
            ) : (
              <>
                <Pressable
                  onPress={() => router.push("/style" as Href)}
                  style={({ pressed }) => [styles.primaryAction, pressed ? styles.pressed : null]}
                >
                  <Feather color={colors.white} name="camera" size={18} />
                  <AppText color={colors.white} style={styles.primaryActionLabel}>
                    Log Outfit with This Item
                  </AppText>
                </Pressable>

                <Pressable
                  onPress={() => router.push(`/closet/${itemId}/edit` as Href)}
                  style={({ pressed }) => [styles.secondaryAction, pressed ? styles.pressed : null]}
                >
                  <Feather color={palette.darkText} name="edit-3" size={16} />
                  <AppText color={palette.darkText} style={styles.secondaryActionLabel}>
                    Edit Item
                  </AppText>
                </Pressable>

                <Pressable
                  onPress={() => void archiveItem()}
                  style={({ pressed }) => [styles.dangerAction, pressed ? styles.pressed : null]}
                >
                  <AppText color={palette.destructive} style={styles.dangerLabel}>
                    {detail.isArchiving ? "Archiving..." : "Archive Item"}
                  </AppText>
                </Pressable>
              </>
            )}
          </View>
        </ScrollView>
      </View>

      <ModalSheet
        onClose={() => setSelectedField(null)}
        visible={Boolean(selectedField)}
      >
        <AppText color={palette.darkText} style={styles.sheetTitle}>
          {selectedField?.label}
        </AppText>
        <AppText color={palette.warmGray} style={styles.sheetBody}>
          {selectedField?.value}
        </AppText>
      </ModalSheet>

      <ModalSheet onClose={() => setMenuOpen(false)} visible={menuOpen}>
        <AppText color={palette.darkText} style={styles.sheetTitle}>
          Options
        </AppText>
        <View style={styles.menuStack}>
          {detail.detail.lifecycle_status !== "archived" ? (
            <>
              <MenuRow
                label="View Similar Items"
                onPress={() => {
                  setMenuOpen(false);
                  router.push(`/closet/${itemId}/similar` as Href);
                }}
              />
              <MenuRow
                label="View History"
                onPress={() => {
                  setMenuOpen(false);
                  router.push(`/closet/${itemId}/history` as Href);
                }}
              />
              <MenuRow
                label="Edit Item"
                onPress={() => {
                  setMenuOpen(false);
                  router.push(`/closet/${itemId}/edit` as Href);
                }}
              />
              <MenuRow
                destructive
                label="Archive Item"
                onPress={() => {
                  setMenuOpen(false);
                  void archiveItem();
                }}
              />
            </>
          ) : (
            <MenuRow
              label="Restore Item"
              onPress={() => {
                setMenuOpen(false);
                void restoreItem();
              }}
            />
          )}
        </View>
      </ModalSheet>

      <ModalSheet onClose={() => setActionMessage(null)} visible={Boolean(actionMessage)}>
        <AppText color={palette.darkText} style={styles.sheetTitle}>
          Note
        </AppText>
        <AppText color={palette.warmGray} style={styles.sheetBody}>
          {actionMessage}
        </AppText>
      </ModalSheet>
    </>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <AppText color={palette.muted} style={styles.sectionLabel}>
      {label}
    </AppText>
  );
}

function MenuRow({
  destructive = false,
  label,
  onPress
}: {
  destructive?: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.menuRow, pressed ? styles.pressed : null]}>
      <AppText color={destructive ? palette.destructive : palette.darkText} style={styles.menuLabel}>
        {label}
      </AppText>
      <Feather color={destructive ? palette.destructive : palette.muted} name="chevron-right" size={16} />
    </Pressable>
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
    paddingHorizontal: 20,
    paddingTop: 40,
    gap: 20
  },
  floatingHeader: {
    position: "absolute",
    top: 56,
    left: 20,
    right: 20,
    zIndex: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  floatingButton: {
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
  counterLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18
  },
  scrollContent: {
    paddingTop: 100,
    paddingBottom: 48
  },
  heroWrap: {
    paddingHorizontal: 20
  },
  heroCard: {
    borderRadius: 22,
    overflow: "hidden",
    backgroundColor: palette.secondary,
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 1,
    shadowRadius: 24,
    elevation: 8
  },
  heroImage: {
    width: "100%",
    aspectRatio: 4 / 5
  },
  imageFallback: {
    borderWidth: 1,
    borderColor: palette.border
  },
  paginationRow: {
    marginTop: 18,
    marginBottom: 22,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6
  },
  paginationDot: {
    width: 5,
    height: 5,
    borderRadius: 999,
    backgroundColor: palette.border
  },
  paginationActive: {
    width: 20,
    height: 5,
    borderRadius: 999,
    backgroundColor: palette.darkText
  },
  metaSection: {
    paddingHorizontal: 24,
    marginBottom: 32
  },
  statusCard: {
    marginHorizontal: 24,
    marginBottom: 18,
    borderRadius: 18,
    backgroundColor: palette.surface,
    padding: 16,
    gap: 4,
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 14,
    elevation: 4
  },
  statusTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18
  },
  statusBody: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 17
  },
  imageStrip: {
    gap: 10,
    paddingHorizontal: 24,
    paddingBottom: 8
  },
  imageThumbShell: {
    width: 72,
    height: 88,
    borderRadius: 18,
    padding: 3,
    backgroundColor: palette.surface
  },
  imageThumbShellActive: {
    borderWidth: 1,
    borderColor: palette.darkText
  },
  imageThumb: {
    width: "100%",
    height: "100%",
    borderRadius: 14
  },
  title: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 26,
    lineHeight: 31,
    letterSpacing: -0.8
  },
  metaLine: {
    marginTop: 6,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 18
  },
  sectionLabel: {
    paddingHorizontal: 24,
    marginBottom: 12,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.2,
    textTransform: "uppercase"
  },
  sectionCard: {
    marginHorizontal: 24,
    marginBottom: 28,
    borderRadius: 20,
    backgroundColor: palette.surface,
    overflow: "hidden",
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 14,
    elevation: 4
  },
  detailRow: {
    paddingHorizontal: 20,
    paddingVertical: 15
  },
  detailLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18
  },
  detailValueRow: {
    marginTop: 6,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12
  },
  detailValue: {
    flex: 1,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  divider: {
    position: "absolute",
    left: 20,
    right: 20,
    bottom: 0,
    height: 1,
    backgroundColor: palette.border
  },
  usageRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: 20
  },
  usageBlock: {
    flex: 1
  },
  usageCount: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 28,
    lineHeight: 31
  },
  usageValue: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  usageCaption: {
    marginTop: 4,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
  },
  usageDivider: {
    width: 1,
    height: 40,
    backgroundColor: palette.border
  },
  frequencyShell: {
    borderTopWidth: 1,
    borderTopColor: palette.border,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 18,
    gap: 10
  },
  frequencyLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1.1,
    textTransform: "uppercase"
  },
  frequencyRow: {
    flexDirection: "row",
    gap: 4
  },
  frequencyBar: {
    flex: 1,
    height: 6,
    borderRadius: 999,
    backgroundColor: palette.border
  },
  frequencyBarActive: {
    backgroundColor: palette.darkText
  },
  usageEmpty: {
    paddingHorizontal: 20,
    paddingVertical: 20,
    gap: 4
  },
  quickLinkRow: {
    flexDirection: "row",
    gap: 12,
    paddingHorizontal: 24,
    marginBottom: 24
  },
  quickLinkButton: {
    flex: 1,
    minHeight: 44,
    borderRadius: 18,
    backgroundColor: palette.surface,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 12,
    elevation: 3
  },
  quickLinkLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 17
  },
  actions: {
    gap: 12,
    paddingHorizontal: 24
  },
  primaryAction: {
    minHeight: 52,
    borderRadius: 18,
    backgroundColor: palette.darkText,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    shadowColor: "rgba(15, 23, 42, 0.14)",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 1,
    shadowRadius: 18,
    elevation: 6
  },
  primaryActionLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  secondaryAction: {
    minHeight: 48,
    borderRadius: 18,
    backgroundColor: palette.secondary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  secondaryActionLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  dangerAction: {
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center"
  },
  dangerLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18
  },
  sheetTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 22,
    lineHeight: 26
  },
  sheetBody: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 22
  },
  menuStack: {
    gap: 2
  },
  menuRow: {
    minHeight: 52,
    borderRadius: 16,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  menuLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20
  },
  emptyStateCard: {
    width: "100%",
    borderRadius: 28,
    backgroundColor: palette.surface,
    paddingHorizontal: 24,
    paddingVertical: 28,
    gap: 14,
    alignItems: "center",
    shadowColor: palette.shadow,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 1,
    shadowRadius: 24,
    elevation: 6
  },
  emptyTitle: {
    textAlign: "center",
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 24,
    lineHeight: 28
  },
  emptyCopy: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    textAlign: "center"
  },
  emptyActions: {
    flexDirection: "row",
    gap: 10
  },
  emptyActionButton: {
    minWidth: 108,
    height: 42,
    paddingHorizontal: 18,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.surface
  },
  emptyActionButtonPrimary: {
    backgroundColor: palette.darkText,
    borderColor: palette.darkText
  },
  emptyActionLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 16
  },
  emptyActionLabelPrimary: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 16,
    color: colors.white
  },
  pressed: {
    opacity: 0.78
  }
});
