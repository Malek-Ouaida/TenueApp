import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, type Href } from "expo-router";
import { useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { AppText } from "../ui";
import {
  CATEGORY_LABELS,
  CLOSET_ITEMS,
  getCategoryCounts,
  getColorCounts
} from "../lib/reference/wardrobe";
import { GlassIconButton } from "../ui/feature-components";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";

export default function StatsDetailsScreen() {
  const [expandedSection, setExpandedSection] = useState<string | null>("most-worn");

  function push(href: string) {
    router.push(href as Href);
  }

  const categoryCounts = getCategoryCounts();
  const totalItems = CLOSET_ITEMS.length;
  const colorCounts = getColorCounts();
  const mostWorn = [...CLOSET_ITEMS].sort((left, right) => right.timesWorn - left.timesWorn).slice(0, 5);
  const leastWorn = [...CLOSET_ITEMS].sort((left, right) => left.timesWorn - right.timesWorn).slice(0, 5);
  const staleItems = CLOSET_ITEMS.filter((item) => (item.lastWornDaysAgo ?? 999) > 30);

  const sections = useMemo(
    () => [
      {
        id: "most-worn",
        title: "Most worn",
        subtitle: "Your go-to pieces",
        items: mostWorn,
        tint: "rgba(255, 239, 161, 0.35)",
        icon: <MaterialCommunityIcons color={featurePalette.foreground} name="crown-outline" size={16} />
      },
      {
        id: "least-worn",
        title: "Least worn",
        subtitle: "Might need attention",
        items: leastWorn,
        tint: "rgba(232, 219, 255, 0.35)",
        icon: <Feather color={featurePalette.foreground} name="trending-down" size={16} />
      },
      {
        id: "stale",
        title: "Not worn in 30+ days",
        subtitle: "Consider wearing or archiving",
        items: staleItems,
        tint: "rgba(255, 107, 107, 0.18)",
        icon: <Feather color={featurePalette.foreground} name="clock" size={16} />
      }
    ],
    [leastWorn, mostWorn, staleItems]
  );

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
      </View>

      <View style={styles.titleBlock}>
        <AppText style={styles.title}>Insights</AppText>
        <AppText style={styles.subtitle}>A deeper look at your wardrobe</AppText>
      </View>

      <View style={styles.block}>
        <AppText style={styles.blockLabel}>Category mix</AppText>
        <View style={[styles.surfaceCard, featureShadows.sm]}>
          {Object.entries(categoryCounts)
            .sort((left, right) => right[1] - left[1])
            .map(([category, count]) => (
              <View key={category} style={styles.mixRow}>
                <View style={styles.mixHead}>
                  <AppText style={styles.mixLabel}>{CATEGORY_LABELS[category] ?? category}</AppText>
                  <AppText style={styles.mixValue}>
                    {count} ({Math.round((count / totalItems) * 100)}%)
                  </AppText>
                </View>
                <View style={styles.mixTrack}>
                  <View style={[styles.mixFill, { width: `${(count / totalItems) * 100}%` }]} />
                </View>
              </View>
            ))}
        </View>
      </View>

      <View style={styles.block}>
        <AppText style={styles.blockLabel}>Your palette</AppText>
        <View style={[styles.surfaceCard, featureShadows.sm]}>
          <View style={styles.paletteRow}>
            {Object.entries(colorCounts)
              .sort((left, right) => right[1] - left[1])
              .map(([color, count]) => (
                <View key={color} style={styles.paletteChip}>
                  <AppText style={styles.paletteChipLabel}>
                    {color} ({count})
                  </AppText>
                </View>
              ))}
          </View>
        </View>
      </View>

      {sections.map((section) => (
        <View key={section.id} style={styles.block}>
          <Pressable
            onPress={() =>
              setExpandedSection((current) => (current === section.id ? null : section.id))
            }
            style={({ pressed }) => [
              styles.insightCard,
              featureShadows.sm,
              pressed ? styles.pressedWide : null
            ]}
          >
            <View style={styles.insightHead}>
              <View style={[styles.insightIcon, { backgroundColor: section.tint }]}>{section.icon}</View>
              <View style={styles.insightCopy}>
                <AppText style={styles.insightTitle}>{section.title}</AppText>
                <AppText style={styles.insightSubtitle}>{section.subtitle}</AppText>
              </View>
              <AppText style={styles.insightCount}>{section.items.length}</AppText>
            </View>
          </Pressable>

          {expandedSection === section.id ? (
            <View style={styles.insightRows}>
              {section.items.map((item) => (
                <Pressable
                  key={item.id}
                  onPress={() => push(`/closet/${item.id}`)}
                  style={({ pressed }) => [
                    styles.insightRow,
                    pressed ? styles.pressedWide : null
                  ]}
                >
                  <Image contentFit="cover" source={item.image} style={styles.insightRowImage} />
                  <View style={styles.insightRowCopy}>
                    <AppText numberOfLines={1} style={styles.insightRowTitle}>
                      {item.title}
                    </AppText>
                    <AppText style={styles.insightRowSubtitle}>
                      Worn {item.timesWorn}× ·{" "}
                      {item.lastWornDaysAgo !== null ? `${item.lastWornDaysAgo}d ago` : "Never worn"}
                    </AppText>
                  </View>
                </Pressable>
              ))}
            </View>
          ) : null}
        </View>
      ))}

      <View style={styles.block}>
        <AppText style={styles.blockLabel}>Wardrobe gaps</AppText>
        <View style={[styles.surfaceCard, featureShadows.sm]}>
          {[
            "A versatile white sneaker",
            "A lightweight summer jacket",
            "A neutral crossbody bag"
          ].map((gap) => (
            <View key={gap} style={styles.gapRow}>
              <View style={styles.gapDot} />
              <AppText style={styles.gapLabel}>{gap}</AppText>
            </View>
          ))}
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
  content: {
    paddingTop: 56,
    paddingHorizontal: 20,
    paddingBottom: 32
  },
  header: {
    marginBottom: 8
  },
  titleBlock: {
    marginBottom: 24,
    paddingHorizontal: 4
  },
  title: {
    ...featureTypography.display
  },
  subtitle: {
    ...featureTypography.body,
    marginTop: 4
  },
  block: {
    marginBottom: 24
  },
  blockLabel: {
    ...featureTypography.microUpper,
    marginBottom: 12,
    paddingHorizontal: 4
  },
  surfaceCard: {
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    padding: 20,
    gap: 12
  },
  mixRow: {
    gap: 6
  },
  mixHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center"
  },
  mixLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  mixValue: {
    fontFamily: "Manrope_500Medium",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  mixTrack: {
    height: 6,
    borderRadius: 999,
    backgroundColor: featurePalette.secondary,
    overflow: "hidden"
  },
  mixFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: "rgba(15, 23, 42, 0.3)"
  },
  paletteRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  paletteChip: {
    borderRadius: 999,
    backgroundColor: featurePalette.secondary,
    paddingHorizontal: 12,
    paddingVertical: 8
  },
  paletteChipLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  insightCard: {
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    padding: 20
  },
  insightHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  insightIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center"
  },
  insightCopy: {
    flex: 1
  },
  insightTitle: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  insightSubtitle: {
    ...featureTypography.label
  },
  insightCount: {
    ...featureTypography.label,
    fontSize: 13,
    lineHeight: 18
  },
  insightRows: {
    paddingTop: 8,
    paddingHorizontal: 8,
    gap: 8
  },
  insightRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 6
  },
  insightRowImage: {
    width: 48,
    height: 48,
    borderRadius: 12
  },
  insightRowCopy: {
    flex: 1
  },
  insightRowTitle: {
    fontFamily: "Manrope_500Medium",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  insightRowSubtitle: {
    ...featureTypography.label,
    marginTop: 2
  },
  gapRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  gapDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "rgba(100, 116, 139, 0.3)"
  },
  gapLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
