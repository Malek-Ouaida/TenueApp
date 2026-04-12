import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useFocusEffect, useLocalSearchParams, type Href } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "../auth/provider";
import { formatDateTime, humanizeEnum } from "../lib/format";
import { AppText } from "../ui";
import { GlassIconButton, PrimaryActionButton, SecondaryActionButton } from "../ui/feature-components";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";
import { useLookbookEntryDetail } from "./hooks";
import { buildLookbookHeroUri } from "./types";
import { formatLocalDate, getLocalTimeZone } from "../wear/dates";

function push(href: string) {
  router.push(href as Href);
}

export default function LookbookDetailScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { session } = useAuth();
  const insets = useSafeAreaInsets();
  const look = useLookbookEntryDetail(session?.access_token, id);
  const [showMenu, setShowMenu] = useState(false);
  const refreshRef = useRef(look.refresh);

  useEffect(() => {
    refreshRef.current = look.refresh;
  }, [look.refresh]);

  useFocusEffect(
    useCallback(() => {
      void refreshRef.current();
    }, [])
  );

  if (look.isLoading && !look.detail) {
    return (
      <View style={styles.loadingScreen}>
        <AppText style={styles.loadingTitle}>Loading look</AppText>
        <AppText style={styles.loadingBody}>Bringing back the photo, tags, and linked closet items.</AppText>
      </View>
    );
  }

  if (!look.detail) {
    return (
      <View style={styles.loadingScreen}>
        <AppText style={styles.loadingTitle}>Look unavailable</AppText>
        <AppText style={styles.loadingBody}>{look.error ?? "This look could not be loaded."}</AppText>
        <PrimaryActionButton label="Back to lookbook" onPress={() => router.replace("/lookbook" as Href)} />
      </View>
    );
  }

  const entry = look.detail;
  const heroUri = buildLookbookHeroUri(entry);
  const dateLabel =
    entry.source_kind === "wear_log" && entry.source_snapshot
      ? `Saved from daily log on ${new Intl.DateTimeFormat(undefined, {
          month: "long",
          day: "numeric",
          year: "numeric"
        }).format(new Date(`${entry.source_snapshot.wear_date}T12:00:00`))}`
      : formatDateTime(entry.published_at ?? entry.updated_at);
  const title =
    entry.title ??
    entry.caption ??
    (entry.source_kind === "wear_log"
      ? "Saved daily look"
      : entry.intent === "recreate"
        ? "Recreate look"
        : "Inspiration");

  async function handleWearThisLook() {
    const created = await look.startWearLog({
      wear_date: formatLocalDate(new Date()),
      timezone_name: getLocalTimeZone()
    });
    if (created) {
      router.replace(`/wear/${created.id}` as Href);
    }
  }

  async function handleArchive() {
    Alert.alert(
      "Archive this look?",
      "Archived looks disappear from the main feed but stay readable in detail screens.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Archive",
          style: "destructive",
          onPress: () => {
            void (async () => {
              const archived = await look.archive();
              if (archived !== null) {
                setShowMenu(false);
              }
            })();
          }
        }
      ]
    );
  }

  async function handleDelete() {
    Alert.alert(
      "Delete this look?",
      "This removes the lookbook entry only. It will not delete the source wear log or the uploaded media asset.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            void (async () => {
              const deleted = await look.remove();
              if (deleted !== null) {
                router.replace("/lookbook" as Href);
              }
            })();
          }
        }
      ]
    );
  }

  return (
    <ScrollView
      bounces={false}
      contentContainerStyle={[styles.screenContent, { paddingBottom: insets.bottom + 36 }]}
      contentInsetAdjustmentBehavior="never"
      showsVerticalScrollIndicator={false}
      style={styles.screen}
    >
      <View style={styles.hero}>
        {heroUri ? (
          <Image contentFit="cover" source={{ uri: heroUri }} style={styles.heroImage} />
        ) : (
          <View style={styles.heroPlaceholder}>
            <Feather color={featurePalette.muted} name="image" size={28} />
          </View>
        )}
        <View style={styles.heroOverlay} />
        <View style={[styles.heroTopRow, { top: insets.top + 16 }]}>
          <GlassIconButton
            icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
            onPress={() => router.back()}
          />
          <View style={styles.menuAnchor}>
            <GlassIconButton
              icon={<Feather color={featurePalette.foreground} name="more-horizontal" size={18} />}
              onPress={() => setShowMenu((current) => !current)}
            />
            {showMenu ? (
              <>
                <Pressable onPress={() => setShowMenu(false)} style={StyleSheet.absoluteFillObject} />
                <View style={[styles.menuSheet, featureShadows.lg]}>
                  {!entry.archived_at ? (
                    <Pressable
                      onPress={() => {
                        setShowMenu(false);
                        push(`/lookbook/add?entryId=${entry.id}`);
                      }}
                      style={styles.menuItem}
                    >
                      <Feather color={featurePalette.foreground} name="edit-3" size={16} />
                      <AppText style={styles.menuLabel}>Edit look</AppText>
                    </Pressable>
                  ) : null}
                  {!entry.archived_at ? (
                    <Pressable onPress={() => void handleArchive()} style={styles.menuItem}>
                      <Feather color={featurePalette.foreground} name="archive" size={16} />
                      <AppText style={styles.menuLabel}>Archive</AppText>
                    </Pressable>
                  ) : null}
                  <Pressable onPress={() => void handleDelete()} style={styles.menuItem}>
                    <Feather color={featurePalette.danger} name="trash-2" size={16} />
                    <AppText style={styles.menuDeleteLabel}>Delete</AppText>
                  </Pressable>
                </View>
              </>
            ) : null}
          </View>
        </View>
      </View>

      <View style={styles.content}>
        <View style={styles.titleBlock}>
          <View style={styles.badgeRow}>
            <View style={styles.badge}>
              <AppText style={styles.badgeLabel}>
                {entry.status === "draft" ? "Draft" : humanizeEnum(entry.intent)}
              </AppText>
            </View>
            <View style={styles.badgeMuted}>
              <AppText style={styles.badgeMutedLabel}>{humanizeEnum(entry.source_kind)}</AppText>
            </View>
          </View>
          <AppText style={styles.title}>{title}</AppText>
          <AppText style={styles.meta}>{dateLabel}</AppText>
          {entry.caption && entry.caption !== entry.title ? (
            <AppText style={styles.caption}>{entry.caption}</AppText>
          ) : null}
        </View>

        {look.error ? (
          <View style={styles.noticeCard}>
            <AppText style={styles.noticeTitle}>Action failed</AppText>
            <AppText style={styles.noticeBody}>{look.error}</AppText>
            <View style={styles.noticeAction}>
              <SecondaryActionButton
                label="Refresh"
                onPress={() => void look.refresh()}
                icon={<Feather color={featurePalette.foreground} name="refresh-cw" size={16} />}
              />
            </View>
          </View>
        ) : null}

        {entry.archived_at ? (
          <View style={styles.noticeCard}>
            <AppText style={styles.noticeTitle}>Archived</AppText>
            <AppText style={styles.noticeBody}>This look is hidden from the main feed until you unarchive it in the backend.</AppText>
          </View>
        ) : null}

        <View style={styles.actions}>
          <PrimaryActionButton
            disabled={!entry.has_linked_items || Boolean(entry.archived_at) || look.isMutating}
            label={look.isMutating ? "Starting..." : "Wear This Look"}
            onPress={() => void handleWearThisLook()}
            icon={<Feather color="#FFFFFF" name="repeat" size={16} />}
          />
          {!entry.archived_at ? (
            <SecondaryActionButton
              label="Edit"
              onPress={() => push(`/lookbook/add?entryId=${entry.id}`)}
              icon={<Feather color={featurePalette.foreground} name="edit-3" size={16} />}
            />
          ) : null}
        </View>

        <View style={styles.section}>
          <AppText style={styles.sectionTitle}>Tags</AppText>
          <View style={styles.tagWrap}>
            {[entry.occasion_tag, entry.season_tag, entry.style_tag]
              .filter(Boolean)
              .map((value) => (
                <View key={value} style={styles.tagChip}>
                  <AppText style={styles.tagChipLabel}>{humanizeEnum(value)}</AppText>
                </View>
              ))}
            {!entry.occasion_tag && !entry.season_tag && !entry.style_tag ? (
              <View style={styles.noticeCard}>
                <AppText style={styles.noticeBody}>No tags yet. Add occasion, season, or style tags to make the look easier to find later.</AppText>
              </View>
            ) : null}
          </View>
        </View>

        {(entry.notes ?? entry.source_snapshot?.notes) ? (
          <View style={styles.section}>
            <AppText style={styles.sectionTitle}>Notes</AppText>
            <View style={styles.noticeCard}>
              <AppText style={styles.noticeBody}>{entry.notes ?? entry.source_snapshot?.notes}</AppText>
            </View>
          </View>
        ) : null}

        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <AppText style={styles.sectionTitle}>Linked closet items</AppText>
            <AppText style={styles.sectionMeta}>{entry.linked_item_count} linked</AppText>
          </View>
          {entry.linked_items.length > 0 ? (
            <View style={styles.itemList}>
              {entry.linked_items.map((item) => (
                <Pressable
                  key={`${item.closet_item_id}-${item.sort_index}`}
                  onPress={() => push(`/closet/${item.closet_item_id}`)}
                  style={({ pressed }) => [styles.itemCard, featureShadows.sm, pressed ? styles.pressed : null]}
                >
                  <View style={styles.itemImageFrame}>
                    {item.display_image?.url || item.thumbnail_image?.url ? (
                      <Image
                        contentFit="cover"
                        source={{ uri: item.display_image?.url ?? item.thumbnail_image?.url ?? "" }}
                        style={styles.itemImage}
                      />
                    ) : (
                      <View style={styles.itemFallback}>
                        <Feather color={featurePalette.muted} name="image" size={16} />
                      </View>
                    )}
                  </View>
                  <View style={styles.itemCopy}>
                    <AppText style={styles.itemTitle}>{item.title ?? "Closet item"}</AppText>
                    <AppText style={styles.itemMeta}>
                      {[item.primary_color, humanizeEnum(item.subcategory ?? item.category ?? item.role ?? "item")]
                        .filter(Boolean)
                        .join(" · ")}
                    </AppText>
                  </View>
                  <Feather color={featurePalette.muted} name="chevron-right" size={18} />
                </Pressable>
              ))}
            </View>
          ) : entry.source_kind === "gallery_photo" ? (
            <View style={styles.noticeCard}>
              <AppText style={styles.noticeTitle}>Link closet items</AppText>
              <AppText style={styles.noticeBody}>Add closet items to this look so you can spin it back into wear logging later.</AppText>
              {!entry.archived_at ? (
                <View style={styles.noticeAction}>
                  <SecondaryActionButton
                    label="Link closet items"
                    onPress={() => push(`/lookbook/add?entryId=${entry.id}`)}
                    icon={<Feather color={featurePalette.foreground} name="plus" size={16} />}
                  />
                </View>
              ) : null}
            </View>
          ) : (
            <View style={styles.noticeCard}>
              <AppText style={styles.noticeBody}>This look does not have a usable outfit yet. Edit it if you need to relink the closet items.</AppText>
            </View>
          )}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  screenContent: {
    flexGrow: 1
  },
  hero: {
    aspectRatio: 3 / 4,
    position: "relative",
    backgroundColor: featurePalette.secondary
  },
  heroImage: {
    width: "100%",
    height: "100%"
  },
  heroPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  heroOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.14)"
  },
  heroTopRow: {
    position: "absolute",
    top: 56,
    left: 20,
    right: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  menuAnchor: {
    position: "relative"
  },
  menuSheet: {
    position: "absolute",
    right: 0,
    top: 48,
    width: 168,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    paddingVertical: 8
  },
  menuItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 12
  },
  menuLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  menuDeleteLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.danger
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 24,
    gap: 24
  },
  titleBlock: {
    gap: 10
  },
  badgeRow: {
    flexDirection: "row",
    gap: 8
  },
  badge: {
    borderRadius: 999,
    backgroundColor: featurePalette.foreground,
    paddingHorizontal: 12,
    paddingVertical: 6
  },
  badgeLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 11,
    lineHeight: 14,
    color: "#FFFFFF"
  },
  badgeMuted: {
    borderRadius: 999,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 12,
    paddingVertical: 6,
    ...featureShadows.sm
  },
  badgeMutedLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.foreground
  },
  title: {
    ...featureTypography.title
  },
  meta: {
    ...featureTypography.label
  },
  caption: {
    ...featureTypography.body,
    color: featurePalette.foreground
  },
  actions: {
    gap: 12
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
    ...featureTypography.label
  },
  tagWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  tagChip: {
    borderRadius: 999,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 12,
    paddingVertical: 8,
    ...featureShadows.sm
  },
  tagChipLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 13,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  noticeCard: {
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
  itemList: {
    gap: 10
  },
  itemCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 12
  },
  itemImageFrame: {
    width: 56,
    height: 72,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  itemImage: {
    width: "100%",
    height: "100%"
  },
  itemFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  itemCopy: {
    flex: 1
  },
  itemTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  itemMeta: {
    ...featureTypography.label,
    marginTop: 4
  },
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
    backgroundColor: featurePalette.background,
    gap: 10
  },
  loadingTitle: {
    ...featureTypography.title,
    textAlign: "center"
  },
  loadingBody: {
    ...featureTypography.body,
    textAlign: "center"
  },
  pressed: {
    transform: [{ scale: 0.98 }]
  }
});
