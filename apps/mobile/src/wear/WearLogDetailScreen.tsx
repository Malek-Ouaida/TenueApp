import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { useAuth } from "../auth/provider";
import { humanizeEnum } from "../lib/format";
import { AppText } from "../ui";
import { GlassIconButton, PrimaryActionButton } from "../ui/feature-components";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";
import { useWearLogDetail } from "./hooks";
import type { WearDetectedItemSnapshot, WearItemRoleValue } from "./types";

const WEAR_ITEM_ROLES = new Set<WearItemRoleValue>([
  "top",
  "bottom",
  "dress",
  "outerwear",
  "shoes",
  "bag",
  "accessory",
  "other"
]);

function normalizeWearRole(value: string | null | undefined): WearItemRoleValue | null {
  return value && WEAR_ITEM_ROLES.has(value as WearItemRoleValue)
    ? (value as WearItemRoleValue)
    : null;
}

function formatWearDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric"
  }).format(new Date(`${value}T12:00:00`));
}

function buildHeroUri(detail: {
  primary_photo?: { url: string } | null;
  cover_image?: { url: string } | null;
  items: Array<{
    display_image?: { url: string } | null;
    thumbnail_image?: { url: string } | null;
  }>;
}) {
  return (
    detail.primary_photo?.url ??
    detail.cover_image?.url ??
    detail.items[0]?.display_image?.url ??
    detail.items[0]?.thumbnail_image?.url ??
    null
  );
}

export default function WearLogDetailScreen() {
  const { wearLogId } = useLocalSearchParams<{ wearLogId?: string }>();
  const { session } = useAuth();
  const wearLog = useWearLogDetail(session?.access_token, wearLogId);
  const [selectedMatches, setSelectedMatches] = useState<Record<string, string | null>>({});
  const [excludedDetectedItems, setExcludedDetectedItems] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!wearLog.detail || wearLog.detail.status !== "needs_review") {
      return;
    }

    const nextSelectedMatches: Record<string, string | null> = {};
    const nextExcluded: Record<string, boolean> = {};

    for (const detectedItem of wearLog.detail.detected_items) {
      const linkedItem = wearLog.detail.items.find(
        (item) => item.detected_item_id === detectedItem.id
      );
      nextSelectedMatches[detectedItem.id] =
        linkedItem?.closet_item_id ?? detectedItem.candidate_matches[0]?.closet_item_id ?? null;
      nextExcluded[detectedItem.id] = detectedItem.status === "excluded";
    }

    setSelectedMatches(nextSelectedMatches);
    setExcludedDetectedItems(nextExcluded);
  }, [wearLog.detail?.id, wearLog.detail?.review_version, wearLog.detail?.status]);

  const confirmDisabled = useMemo(() => {
    if (!wearLog.detail || wearLog.detail.status !== "needs_review") {
      return true;
    }

    return wearLog.detail.detected_items.some((detectedItem) => {
      if (excludedDetectedItems[detectedItem.id]) {
        return false;
      }

      return !selectedMatches[detectedItem.id];
    });
  }, [excludedDetectedItems, selectedMatches, wearLog.detail]);

  async function handleConfirmReview() {
    if (!wearLog.detail || wearLog.detail.status !== "needs_review") {
      return;
    }

    await wearLog.confirm({
      expected_review_version: wearLog.detail.review_version,
      items: wearLog.detail.detected_items.flatMap((detectedItem, index) => {
        if (excludedDetectedItems[detectedItem.id]) {
          return [];
        }

        const closetItemId = selectedMatches[detectedItem.id];
        if (!closetItemId) {
          return [];
        }

        return [
          {
            closet_item_id: closetItemId,
            detected_item_id: detectedItem.id,
            role: normalizeWearRole(detectedItem.predicted_role),
            sort_index: index,
            source: "ai_matched"
          }
        ];
      }),
      resolved_detected_items: wearLog.detail.detected_items
        .filter((detectedItem) => excludedDetectedItems[detectedItem.id])
        .map((detectedItem) => ({
          detected_item_id: detectedItem.id,
          status: "excluded" as const
        }))
    });
  }

  async function handleDelete() {
    const deleted = await wearLog.remove();
    if (deleted !== null) {
      router.replace("/wear" as Href);
    }
  }

  if (wearLog.isLoading && !wearLog.detail) {
    return (
      <View style={styles.loadingScreen}>
        <AppText style={styles.loadingTitle}>Loading wear log</AppText>
        <AppText style={styles.loadingBody}>Bringing back the outfit details and review state.</AppText>
      </View>
    );
  }

  if (!wearLog.detail) {
    return (
      <View style={styles.loadingScreen}>
        <AppText style={styles.loadingTitle}>Wear log unavailable</AppText>
        <AppText style={styles.loadingBody}>
          {wearLog.error ?? "This wear log could not be loaded."}
        </AppText>
        <PrimaryActionButton label="Back to history" onPress={() => router.replace("/wear" as Href)} />
      </View>
    );
  }

  const detail = wearLog.detail;
  const heroUri = buildHeroUri(detail);

  return (
    <ScrollView
      bounces={false}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      style={styles.screen}
    >
      <View style={styles.header}>
        <GlassIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
          onPress={() => router.back()}
        />
        <View style={styles.headerActions}>
          {detail.status === "failed" ? (
            <Pressable
              onPress={() => void wearLog.reprocess()}
              style={({ pressed }) => [styles.headerPill, pressed ? styles.pressed : null]}
            >
              <Feather color={featurePalette.foreground} name="refresh-cw" size={14} />
              <AppText style={styles.headerPillLabel}>Retry</AppText>
            </Pressable>
          ) : null}
          <Pressable
            onPress={() => void handleDelete()}
            style={({ pressed }) => [styles.headerPill, pressed ? styles.pressed : null]}
          >
            <Feather color={featurePalette.danger} name="trash-2" size={14} />
            <AppText style={styles.headerDeleteLabel}>Delete</AppText>
          </Pressable>
        </View>
      </View>

      <View style={[styles.heroCard, featureShadows.lg]}>
        {heroUri ? (
          <Image contentFit="cover" source={{ uri: heroUri }} style={styles.heroImage} />
        ) : (
          <View style={styles.heroPlaceholder}>
            <Feather color={featurePalette.muted} name="camera" size={28} />
          </View>
        )}
        <View style={styles.heroOverlay} />
        <View style={styles.heroCopy}>
          <View style={styles.heroPills}>
            <View style={styles.heroPill}>
              <AppText style={styles.heroPillLabel}>{formatWearDate(detail.wear_date)}</AppText>
            </View>
            <View style={[styles.heroPill, styles.heroStatusPill]}>
              <AppText style={styles.heroStatusLabel}>{humanizeEnum(detail.status)}</AppText>
            </View>
          </View>
          <AppText style={styles.heroTitle}>
            {detail.context ? humanizeEnum(detail.context) : "Wear Log"}
          </AppText>
          <AppText style={styles.heroSubtitle}>
            {detail.item_count} items · {detail.is_confirmed ? "Confirmed" : humanizeEnum(detail.source)}
          </AppText>
        </View>
      </View>

      {wearLog.error ? (
        <View style={styles.noticeCard}>
          <AppText style={styles.noticeTitle}>Update failed</AppText>
          <AppText style={styles.noticeBody}>{wearLog.error}</AppText>
        </View>
      ) : null}

      {detail.failure_summary ? (
        <View style={styles.noticeCard}>
          <AppText style={styles.noticeTitle}>Processing issue</AppText>
          <AppText style={styles.noticeBody}>{detail.failure_summary}</AppText>
        </View>
      ) : null}

      {detail.status === "processing" ? (
        <View style={styles.noticeCard}>
          <AppText style={styles.noticeTitle}>Still processing</AppText>
          <AppText style={styles.noticeBody}>
            Tenue is still matching the outfit photo to your closet. This page refreshes automatically.
          </AppText>
        </View>
      ) : null}

      {detail.status === "needs_review" ? (
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <AppText style={styles.sectionTitle}>Review detected items</AppText>
            <AppText style={styles.sectionMeta}>
              {detail.detected_items.length} {detail.detected_items.length === 1 ? "item" : "items"}
            </AppText>
          </View>

          <View style={styles.detectedList}>
            {detail.detected_items.map((detectedItem) => (
              <DetectedItemCard
                key={detectedItem.id}
                detectedItem={detectedItem}
                excluded={excludedDetectedItems[detectedItem.id] ?? false}
                onExcludeToggle={() => {
                  setExcludedDetectedItems((current) => ({
                    ...current,
                    [detectedItem.id]: !current[detectedItem.id]
                  }));
                }}
                onSelectCandidate={(closetItemId) => {
                  setSelectedMatches((current) => ({
                    ...current,
                    [detectedItem.id]: closetItemId
                  }));
                  setExcludedDetectedItems((current) => ({
                    ...current,
                    [detectedItem.id]: false
                  }));
                }}
                selectedClosetItemId={selectedMatches[detectedItem.id] ?? null}
              />
            ))}
          </View>

          <PrimaryActionButton
            disabled={confirmDisabled || wearLog.isMutating}
            label={wearLog.isMutating ? "Saving review…" : "Confirm wear log"}
            onPress={() => void handleConfirmReview()}
          />
        </View>
      ) : null}

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <AppText style={styles.sectionTitle}>Logged items</AppText>
          <AppText style={styles.sectionMeta}>{detail.items.length} linked</AppText>
        </View>

        {detail.items.length === 0 ? (
          <View style={styles.noticeCard}>
            <AppText style={styles.noticeTitle}>No closet items linked yet</AppText>
            <AppText style={styles.noticeBody}>
              Once this wear log is confirmed, the worn closet items will appear here.
            </AppText>
          </View>
        ) : (
          <View style={styles.loggedItemList}>
            {detail.items.map((item) => (
              <Pressable
                key={`${item.closet_item_id}-${item.sort_index}`}
                onPress={() => router.push(`/closet/${item.closet_item_id}` as Href)}
                style={({ pressed }) => [styles.loggedItemCard, featureShadows.sm, pressed ? styles.pressed : null]}
              >
                <View style={styles.loggedItemImageFrame}>
                  {item.display_image?.url || item.thumbnail_image?.url ? (
                    <Image
                      contentFit="cover"
                      source={{ uri: item.display_image?.url ?? item.thumbnail_image?.url ?? "" }}
                      style={styles.loggedItemImage}
                    />
                  ) : (
                    <View style={styles.loggedItemImagePlaceholder}>
                      <Feather color={featurePalette.muted} name="image" size={18} />
                    </View>
                  )}
                </View>
                <View style={styles.loggedItemCopy}>
                  <AppText style={styles.loggedItemTitle}>{item.title ?? "Closet item"}</AppText>
                  <AppText style={styles.loggedItemSubtitle}>
                    {[item.primary_color, humanizeEnum(item.subcategory ?? item.category ?? item.role)]
                      .filter(Boolean)
                      .join(" · ")}
                  </AppText>
                </View>
                <Feather color={featurePalette.muted} name="chevron-right" size={18} />
              </Pressable>
            ))}
          </View>
        )}
      </View>

      {detail.notes ? (
        <View style={styles.section}>
          <AppText style={styles.sectionTitle}>Notes</AppText>
          <View style={styles.noticeCard}>
            <AppText style={styles.noticeBody}>{detail.notes}</AppText>
          </View>
        </View>
      ) : null}
    </ScrollView>
  );
}

function DetectedItemCard({
  detectedItem,
  excluded,
  onExcludeToggle,
  onSelectCandidate,
  selectedClosetItemId
}: {
  detectedItem: WearDetectedItemSnapshot;
  excluded: boolean;
  onExcludeToggle: () => void;
  onSelectCandidate: (closetItemId: string) => void;
  selectedClosetItemId: string | null;
}) {
  return (
    <View style={[styles.detectedCard, featureShadows.sm]}>
      <View style={styles.detectedHeader}>
        <View style={styles.detectedHeaderCopy}>
          <AppText style={styles.detectedTitle}>
            {humanizeEnum(detectedItem.predicted_role ?? detectedItem.predicted_category ?? "Detected item")}
          </AppText>
          <AppText style={styles.detectedSubtitle}>
            {[detectedItem.predicted_subcategory, detectedItem.predicted_colors[0]]
              .filter(Boolean)
              .map((value) => humanizeEnum(value))
              .join(" · ")}
          </AppText>
        </View>
        <Pressable onPress={onExcludeToggle} style={styles.excludeButton}>
          <Feather color={excluded ? "#FFFFFF" : featurePalette.foreground} name="x" size={14} />
        </Pressable>
      </View>

      {detectedItem.crop_image?.url ? (
        <Image contentFit="cover" source={{ uri: detectedItem.crop_image.url }} style={styles.detectedCrop} />
      ) : null}

      <View style={styles.candidateList}>
        {detectedItem.candidate_matches.map((candidate) => {
          const selected = selectedClosetItemId === candidate.closet_item_id && !excluded;
          return (
            <Pressable
              key={candidate.id}
              onPress={() => onSelectCandidate(candidate.closet_item_id)}
              style={[
                styles.candidateCard,
                selected ? styles.candidateCardSelected : null
              ]}
            >
              <View style={styles.candidateImageFrame}>
                {candidate.item?.thumbnail_image?.url || candidate.item?.display_image?.url ? (
                  <Image
                    contentFit="cover"
                    source={{ uri: candidate.item?.thumbnail_image?.url ?? candidate.item?.display_image?.url ?? "" }}
                    style={styles.candidateImage}
                  />
                ) : (
                  <View style={styles.candidateImagePlaceholder}>
                    <Feather color={featurePalette.muted} name="image" size={14} />
                  </View>
                )}
              </View>
              <View style={styles.candidateCopy}>
                <AppText numberOfLines={1} style={styles.candidateTitle}>
                  {candidate.item?.title ?? "Closet item"}
                </AppText>
                <AppText style={styles.candidateSubtitle}>
                  {Math.round(candidate.score * 100)}% match
                </AppText>
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  content: {
    paddingTop: 56,
    paddingHorizontal: 20,
    paddingBottom: 40,
    gap: 18
  },
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    paddingHorizontal: 24,
    backgroundColor: featurePalette.background
  },
  loadingTitle: {
    ...featureTypography.title,
    textAlign: "center"
  },
  loadingBody: {
    ...featureTypography.body,
    textAlign: "center"
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  headerActions: {
    flexDirection: "row",
    gap: 8
  },
  headerPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderRadius: 999,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 12,
    paddingVertical: 10
  },
  headerPillLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  headerDeleteLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.danger
  },
  heroCard: {
    height: 360,
    borderRadius: 28,
    overflow: "hidden",
    backgroundColor: "#FFFFFF"
  },
  heroImage: {
    width: "100%",
    height: "100%"
  },
  heroPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: featurePalette.secondary
  },
  heroOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(15, 23, 42, 0.26)"
  },
  heroCopy: {
    position: "absolute",
    left: 20,
    right: 20,
    bottom: 20,
    gap: 10
  },
  heroPills: {
    flexDirection: "row",
    gap: 8,
    flexWrap: "wrap"
  },
  heroPill: {
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.92)",
    paddingHorizontal: 10,
    paddingVertical: 6
  },
  heroStatusPill: {
    backgroundColor: "rgba(255, 210, 194, 0.95)"
  },
  heroPillLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  heroStatusLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 12,
    lineHeight: 16,
    color: "#A34E1C"
  },
  heroTitle: {
    ...featureTypography.display,
    color: "#FFFFFF",
    fontSize: 30,
    lineHeight: 32
  },
  heroSubtitle: {
    ...featureTypography.body,
    color: "rgba(255,255,255,0.85)"
  },
  noticeCard: {
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 14
  },
  noticeTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.darkText,
    marginBottom: 4
  },
  noticeBody: {
    ...featureTypography.label,
    fontSize: 13,
    lineHeight: 18
  },
  section: {
    gap: 12
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  sectionTitle: {
    ...featureTypography.microUpper
  },
  sectionMeta: {
    ...featureTypography.label,
    fontSize: 12
  },
  detectedList: {
    gap: 12
  },
  detectedCard: {
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    padding: 14,
    gap: 12
  },
  detectedHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12
  },
  detectedHeaderCopy: {
    flex: 1
  },
  detectedTitle: {
    ...featureTypography.bodyStrong
  },
  detectedSubtitle: {
    ...featureTypography.label,
    marginTop: 2
  },
  excludeButton: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: featurePalette.secondary
  },
  detectedCrop: {
    width: "100%",
    aspectRatio: 4 / 3,
    borderRadius: 16
  },
  candidateList: {
    gap: 10
  },
  candidateCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: 16,
    padding: 10,
    backgroundColor: featurePalette.secondary,
    borderWidth: 1.5,
    borderColor: "transparent"
  },
  candidateCardSelected: {
    borderColor: featurePalette.foreground,
    backgroundColor: "#FFFFFF"
  },
  candidateImageFrame: {
    width: 44,
    height: 56,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: "#FFFFFF"
  },
  candidateImage: {
    width: "100%",
    height: "100%"
  },
  candidateImagePlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  candidateCopy: {
    flex: 1
  },
  candidateTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 13,
    lineHeight: 17,
    color: featurePalette.foreground
  },
  candidateSubtitle: {
    ...featureTypography.label,
    marginTop: 2,
    fontSize: 12
  },
  loggedItemList: {
    gap: 12
  },
  loggedItemCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    padding: 12
  },
  loggedItemImageFrame: {
    width: 60,
    height: 76,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  loggedItemImage: {
    width: "100%",
    height: "100%"
  },
  loggedItemImagePlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  loggedItemCopy: {
    flex: 1
  },
  loggedItemTitle: {
    ...featureTypography.bodyStrong
  },
  loggedItemSubtitle: {
    ...featureTypography.label,
    marginTop: 2,
    fontSize: 12
  },
  pressed: {
    transform: [{ scale: 0.99 }]
  }
});
