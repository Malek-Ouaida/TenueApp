import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  PanResponder
} from "react-native";

import { useOutfits } from "../outfits/provider";
import { AppText } from "../ui";
import {
  type OutfitEntry,
  buildTimeline,
  dateKey,
  formatDayName,
  formatFullDate,
  parseDateKey
} from "../lib/reference/wardrobe";
import { GlassIconButton } from "../ui/feature-components";
import { supportsNativeAnimatedDriver } from "../lib/runtime";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";

const SCREEN_WIDTH = Dimensions.get("window").width;

export default function OutfitDetailScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { outfits } = useOutfits();
  const timeline = useMemo(() => buildTimeline(), []);
  const initialDate = id ?? dateKey(new Date());

  const [currentIdx, setCurrentIdx] = useState(() => {
    const found = timeline.indexOf(initialDate);
    return found >= 0 ? found : timeline.length - 1;
  });
  const [showMenu, setShowMenu] = useState(false);
  const [scrollEnabled, setScrollEnabled] = useState(true);
  const offset = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const found = timeline.indexOf(initialDate);
    if (found >= 0) {
      setCurrentIdx(found);
    }
  }, [initialDate, timeline]);

  const currentDateKey = timeline[currentIdx] ?? initialDate;
  const currentDate = parseDateKey(currentDateKey);
  const currentOutfit = outfits[currentDateKey];

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, gestureState) =>
          Math.abs(gestureState.dx) > 12 && Math.abs(gestureState.dx) > Math.abs(gestureState.dy),
        onPanResponderGrant: () => {
          setScrollEnabled(false);
          offset.stopAnimation();
        },
        onPanResponderMove: (_, gestureState) => {
          const atStart = currentIdx === 0 && gestureState.dx > 0;
          const atEnd = currentIdx === timeline.length - 1 && gestureState.dx < 0;
          const dampened = atStart || atEnd ? gestureState.dx * 0.2 : gestureState.dx;
          offset.setValue(dampened);
        },
        onPanResponderRelease: (_, gestureState) => {
          setScrollEnabled(true);
          if (gestureState.dx < -60 && currentIdx < timeline.length - 1) {
            Animated.timing(offset, {
              toValue: -SCREEN_WIDTH,
              duration: 220,
              useNativeDriver: supportsNativeAnimatedDriver
            }).start(() => {
              setCurrentIdx((value) => value + 1);
              offset.setValue(0);
            });
            return;
          }

          if (gestureState.dx > 60 && currentIdx > 0) {
            Animated.timing(offset, {
              toValue: SCREEN_WIDTH,
              duration: 220,
              useNativeDriver: supportsNativeAnimatedDriver
            }).start(() => {
              setCurrentIdx((value) => value - 1);
              offset.setValue(0);
            });
            return;
          }

          Animated.spring(offset, {
            toValue: 0,
            damping: 20,
            mass: 0.8,
            stiffness: 220,
            useNativeDriver: supportsNativeAnimatedDriver
          }).start();
        }
      }),
    [currentIdx, offset, timeline.length]
  );

  return (
    <View style={styles.screen}>
      <View style={styles.floatingHeader}>
        <GlassIconButton
          icon={<Feather color={featurePalette.darkText} name="arrow-left" size={18} />}
          onPress={() => router.back()}
        />

        <View style={[styles.datePill, featureShadows.sm]}>
          <AppText style={styles.datePillLabel}>{formatFullDate(currentDate)}</AppText>
        </View>

        <View style={styles.menuAnchor}>
          <GlassIconButton
            icon={<Feather color={featurePalette.darkText} name="more-horizontal" size={18} />}
            onPress={() => setShowMenu((current) => !current)}
          />

          {showMenu ? (
            <>
              <Pressable onPress={() => setShowMenu(false)} style={StyleSheet.absoluteFillObject} />
              <View style={[styles.menuSheet, featureShadows.lg]}>
                <Pressable
                  onPress={() => {
                    setShowMenu(false);
                    push(`/outfit/${currentDateKey}/edit`);
                  }}
                  style={styles.menuItem}
                >
                  <Feather color={featurePalette.warmGray} name="edit-3" size={16} />
                  <AppText style={styles.menuLabel}>Edit Outfit</AppText>
                </Pressable>
                <Pressable style={styles.menuItem}>
                  <Feather color={featurePalette.danger} name="trash-2" size={16} />
                  <AppText style={styles.menuDeleteLabel}>Delete</AppText>
                </Pressable>
              </View>
            </>
          ) : null}
        </View>
      </View>

      <ScrollView
        bounces={false}
        scrollEnabled={scrollEnabled}
        showsVerticalScrollIndicator={false}
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
      >
        <Animated.View
          {...panResponder.panHandlers}
          style={{
            transform: [
              { translateX: offset },
              {
                rotate: offset.interpolate({
                  inputRange: [-SCREEN_WIDTH, 0, SCREEN_WIDTH],
                  outputRange: ["-15deg", "0deg", "15deg"]
                })
              }
            ]
          }}
        >
          {currentOutfit ? (
            <OutfitContent date={currentDate} dateKey={currentDateKey} outfit={currentOutfit} push={push} />
          ) : (
            <EmptyDay date={currentDate} push={push} />
          )}
        </Animated.View>
      </ScrollView>

      <View style={styles.timelineDots}>
        {[-2, -1, 0, 1, 2].map((relative) => {
          const idx = currentIdx + relative;
          if (idx < 0 || idx >= timeline.length) {
            return null;
          }

          const hasOutfit = Boolean(outfits[timeline[idx] ?? ""]);
          const active = relative === 0;
          return (
            <View
              key={relative}
              style={[
                styles.timelineDot,
                active ? styles.timelineDotActive : null,
                !active && hasOutfit ? styles.timelineDotFilled : null,
                Math.abs(relative) === 2 ? styles.timelineDotEdge : null
              ]}
            />
          );
        })}
      </View>
    </View>
  );
}

function OutfitContent({
  date,
  dateKey: currentDateKey,
  outfit,
  push
}: {
  date: Date;
  dateKey: string;
  outfit: OutfitEntry;
  push: (href: string) => void;
}) {
  const heroOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    heroOpacity.setValue(0);
    Animated.timing(heroOpacity, {
      toValue: 1,
      duration: 320,
      useNativeDriver: supportsNativeAnimatedDriver
    }).start();
  }, [currentDateKey, heroOpacity]);

  return (
    <View style={styles.content}>
      <View style={[styles.heroFrame, featureShadows.lg]}>
        <Animated.View style={[StyleSheet.absoluteFillObject, { opacity: heroOpacity }]}>
          <Image
            contentFit="cover"
            source={outfit.imageUri ? { uri: outfit.imageUri } : outfit.image}
            style={StyleSheet.absoluteFillObject}
          />
        </Animated.View>
        <View style={styles.heroOverlay} />
      </View>

      <View style={styles.dateContext}>
        <AppText style={styles.dayTitle}>{formatDayName(date)}</AppText>
        <View style={styles.dateContextRow}>
          <AppText style={styles.dateContextLabel}>{formatFullDate(date)}</AppText>
          {outfit.occasion ? (
            <>
              <View style={styles.dateDivider} />
              <View style={styles.occasionChip}>
                <AppText style={styles.occasionChipLabel}>{outfit.occasion}</AppText>
              </View>
            </>
          ) : null}
        </View>
      </View>

      <View style={styles.itemsSection}>
        <View style={styles.sectionHeader}>
          <AppText style={styles.sectionLabel}>Worn</AppText>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={styles.itemsRow}>
            {outfit.items.map((item) => (
              <Pressable
                key={item.id}
                onPress={() => push(`/closet/${item.id}`)}
                style={({ pressed }) => [styles.itemCard, pressed ? styles.pressedWide : null]}
              >
                <View style={[styles.itemImageFrame, featureShadows.sm]}>
                  <Image contentFit="cover" source={item.image} style={styles.itemImage} />
                </View>
                <AppText numberOfLines={1} style={styles.itemLabel}>
                  {item.title.split(" ").slice(0, 2).join(" ")}
                </AppText>
              </Pressable>
            ))}
          </View>
        </ScrollView>
      </View>

      {outfit.note ? (
        <View style={styles.noteSection}>
          <AppText style={styles.sectionLabel}>Note</AppText>
          <AppText style={styles.noteCopy}>"{outfit.note}"</AppText>
        </View>
      ) : null}

      <Pressable
        onPress={() => push(`/outfit/${currentDateKey}/edit`)}
        style={({ pressed }) => [styles.editButton, featureShadows.lg, pressed ? styles.pressedWide : null]}
      >
        <Feather color="#FFFFFF" name="edit-3" size={16} />
        <AppText style={styles.editButtonLabel}>Edit Outfit</AppText>
      </Pressable>
    </View>
  );
}

function EmptyDay({ date, push }: { date: Date; push: (href: string) => void }) {
  return (
    <View style={styles.emptyDay}>
      <View style={styles.emptyIcon}>
        <AppText style={styles.emptyIconEmoji}>👔</AppText>
      </View>
      <AppText style={styles.emptyDayTitle}>{formatDayName(date)}</AppText>
      <AppText style={styles.emptyDayDate}>{formatFullDate(date)}</AppText>
      <AppText style={styles.emptyDayCopy}>No outfit logged</AppText>
      <Pressable
        onPress={() => push("/log-outfit")}
        style={({ pressed }) => [styles.emptyDayButton, pressed ? styles.pressedWide : null]}
      >
        <AppText style={styles.emptyDayButtonLabel}>Log outfit</AppText>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
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
  datePill: {
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.9)",
    paddingHorizontal: 16,
    paddingVertical: 8
  },
  datePillLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.darkText
  },
  menuAnchor: {
    position: "relative"
  },
  menuSheet: {
    position: "absolute",
    top: 52,
    right: 0,
    width: 180,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    overflow: "hidden"
  },
  menuItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 14
  },
  menuLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.darkText
  },
  menuDeleteLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.danger
  },
  scroll: {
    flex: 1
  },
  scrollContent: {
    paddingTop: 96,
    paddingBottom: 120
  },
  content: {
    paddingHorizontal: 20
  },
  heroFrame: {
    borderRadius: 20,
    overflow: "hidden",
    aspectRatio: 4 / 5,
    backgroundColor: "#EEF2F7"
  },
  heroOverlay: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 96,
    backgroundColor: "rgba(0,0,0,0.12)"
  },
  dateContext: {
    marginTop: 20,
    paddingHorizontal: 4
  },
  dayTitle: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 22,
    lineHeight: 28,
    color: featurePalette.darkText
  },
  dateContextRow: {
    marginTop: 4,
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  dateContextLabel: {
    ...featureTypography.body,
    fontSize: 14,
    lineHeight: 18
  },
  dateDivider: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#CBD5E1"
  },
  occasionChip: {
    borderRadius: 999,
    backgroundColor: featurePalette.coralSurface,
    paddingHorizontal: 10,
    paddingVertical: 4
  },
  occasionChipLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 13,
    lineHeight: 16,
    color: featurePalette.coral
  },
  itemsSection: {
    marginTop: 28
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
    paddingHorizontal: 4
  },
  sectionLabel: {
    ...featureTypography.microUpper
  },
  itemsRow: {
    flexDirection: "row",
    gap: 12
  },
  itemCard: {
    width: 80
  },
  itemImageFrame: {
    width: 80,
    height: 100,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  itemImage: {
    width: "100%",
    height: "100%"
  },
  itemLabel: {
    marginTop: 6,
    fontFamily: "Manrope_500Medium",
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.warmGray,
    textAlign: "center"
  },
  noteSection: {
    marginTop: 24,
    paddingHorizontal: 4
  },
  noteCopy: {
    ...featureTypography.body,
    fontStyle: "italic",
    marginTop: 8
  },
  editButton: {
    marginTop: 28,
    height: 52,
    borderRadius: 26,
    backgroundColor: featurePalette.darkText,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  editButtonLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 15,
    lineHeight: 20,
    color: "#FFFFFF"
  },
  emptyDay: {
    minHeight: 420,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20
  },
  emptyIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "#F8F8F6",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20
  },
  emptyIconEmoji: {
    fontSize: 32,
    lineHeight: 36
  },
  emptyDayTitle: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 20,
    lineHeight: 24,
    color: featurePalette.darkText,
    marginBottom: 4
  },
  emptyDayDate: {
    ...featureTypography.label,
    fontSize: 14,
    lineHeight: 18
  },
  emptyDayCopy: {
    ...featureTypography.body,
    color: "#CBD5E1",
    marginTop: 4,
    marginBottom: 24
  },
  emptyDayButton: {
    height: 48,
    borderRadius: 24,
    backgroundColor: featurePalette.coral,
    paddingHorizontal: 28,
    alignItems: "center",
    justifyContent: "center"
  },
  emptyDayButtonLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: "#FFFFFF"
  },
  timelineDots: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 32,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6
  },
  timelineDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: "#E8E8E6"
  },
  timelineDotFilled: {
    backgroundColor: "#CBD5E1"
  },
  timelineDotActive: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: featurePalette.coral
  },
  timelineDotEdge: {
    opacity: 0.5
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
  function push(href: string) {
    router.push(href as Href);
  }
