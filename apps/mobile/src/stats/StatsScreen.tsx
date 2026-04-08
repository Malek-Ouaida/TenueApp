import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { router, type Href } from "expo-router";
import type { ReactNode } from "react";
import { ScrollView, Pressable, StyleSheet, View } from "react-native";

import { useOutfits } from "../outfits/provider";
import { AppText } from "../ui";
import {
  CATEGORY_LABELS,
  CLOSET_ITEMS,
  getBrandCounts,
  getCategoryCounts,
  getColorCounts,
  getStreak
} from "../lib/reference/wardrobe";
import { GlassIconButton } from "../ui/feature-components";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";

type StatItem = {
  color: string;
  icon: ReactNode;
  label: string;
  sub?: string;
  value: string;
};

export default function StatsScreen() {
  const { outfits } = useOutfits();
  const totalOutfits = Object.keys(outfits).length;
  const streak = getStreak(outfits);

  const categoryCounts = getCategoryCounts();
  const topCategory = Object.entries(categoryCounts).sort((left, right) => right[1] - left[1])[0];
  const colorCounts = getColorCounts();
  const topColor = Object.entries(colorCounts).sort((left, right) => right[1] - left[1])[0];
  const brandCounts = getBrandCounts();
  const topBrand = Object.entries(brandCounts).sort((left, right) => right[1] - left[1])[0];
  const mostWorn = [...CLOSET_ITEMS].sort((left, right) => right.timesWorn - left.timesWorn)[0];
  const leastWorn = [...CLOSET_ITEMS].sort((left, right) => left.timesWorn - right.timesWorn)[0];

  const sections: Array<{ title: string; items: StatItem[] }> = [
    {
      title: "Overview",
      items: [
        {
          icon: <MaterialCommunityIcons color={featurePalette.foreground} name="hanger" size={20} />,
          label: "Outfits Logged",
          value: `${totalOutfits}`,
          sub: "since January 2026",
          color: featurePalette.sage
        },
        {
          icon: <MaterialCommunityIcons color={featurePalette.coral} name="fire" size={20} />,
          label: "Current Streak",
          value: `${streak} days`,
          sub: "your best: 12 days",
          color: "rgba(255, 107, 107, 0.15)"
        },
        {
          icon: <Feather color={featurePalette.foreground} name="trending-up" size={20} />,
          label: "Avg. Outfits / Week",
          value: `${Math.round((totalOutfits / 12) * 10) / 10}`,
          sub: "last 3 months",
          color: "rgba(216, 235, 207, 0.2)"
        },
        {
          icon: <Feather color="#7BA2FF" name="calendar" size={20} />,
          label: "Member Since",
          value: "January 2026",
          sub: "4 months of style",
          color: "rgba(220, 234, 247, 0.35)"
        }
      ]
    },
    {
      title: "Wardrobe",
      items: [
        {
          icon: <MaterialCommunityIcons color="#7658C3" name="repeat" size={20} />,
          label: "Total Items",
          value: `${CLOSET_ITEMS.length}`,
          sub: "in your closet",
          color: "rgba(232, 219, 255, 0.3)"
        },
        {
          icon: <MaterialCommunityIcons color={featurePalette.foreground} name="chart-bar" size={20} />,
          label: "Top Category",
          value: topCategory ? CATEGORY_LABELS[topCategory[0]] ?? topCategory[0] : "—",
          sub: topCategory ? `${topCategory[1]} items` : "",
          color: featurePalette.secondary
        },
        {
          icon: <MaterialCommunityIcons color="#C78B00" name="palette-outline" size={20} />,
          label: "Most Common Color",
          value: topColor?.[0] ?? "—",
          sub: topColor ? `${topColor[1]} items` : "",
          color: "rgba(255, 239, 161, 0.2)"
        },
        {
          icon: <Feather color={featurePalette.coral} name="tag" size={20} />,
          label: "Favorite Brand",
          value: topBrand?.[0] ?? "—",
          sub: topBrand ? `${topBrand[1]} items` : "",
          color: "rgba(255, 107, 107, 0.12)"
        }
      ]
    },
    {
      title: "Wear Habits",
      items: [
        {
          icon: <MaterialCommunityIcons color="#C78B00" name="crown-outline" size={20} />,
          label: "Most Worn Item",
          value: mostWorn?.title ?? "—",
          sub: mostWorn ? `${mostWorn.timesWorn} times · ${mostWorn.brand}` : "",
          color: "rgba(255, 239, 161, 0.2)"
        },
        {
          icon: <Feather color={featurePalette.muted} name="clock" size={20} />,
          label: "Least Worn Item",
          value: leastWorn?.title ?? "—",
          sub: leastWorn ? `${leastWorn.timesWorn} times · ${leastWorn.brand}` : "",
          color: featurePalette.secondary
        },
        {
          icon: <Feather color="#FFB3C4" name="heart" size={20} />,
          label: "Outfit Repeats",
          value: "3",
          sub: "you wore the same combo",
          color: "rgba(255, 234, 242, 0.35)"
        },
        {
          icon: <Feather color="#C78B00" name="sun" size={20} />,
          label: "Favorite Season",
          value: "All Season",
          sub: "most versatile pieces",
          color: "rgba(255, 239, 161, 0.15)"
        },
        {
          icon: <Feather color="#7658C3" name="moon" size={20} />,
          label: "Favorite Occasion",
          value: "Casual",
          sub: "your comfort zone",
          color: "rgba(232, 219, 255, 0.2)"
        },
        {
          icon: <MaterialCommunityIcons color="#567848" name="star-four-points" size={20} />,
          label: "Style Variety Score",
          value: "7.2 / 10",
          sub: "great range!",
          color: "rgba(216, 235, 207, 0.25)"
        }
      ]
    }
  ];

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
        <AppText style={styles.headerTitle}>Your Stats</AppText>
      </View>

      {sections.map((section) => (
        <View key={section.title} style={styles.section}>
          <AppText style={styles.sectionLabel}>{section.title}</AppText>
          <View style={styles.sectionCards}>
            {section.items.map((item) => (
              <View key={item.label} style={[styles.statCard, featureShadows.sm]}>
                <View style={[styles.statIconShell, { backgroundColor: item.color }]}>{item.icon}</View>
                <View style={styles.statCopy}>
                  <AppText style={styles.statLabel}>{item.label}</AppText>
                  <AppText numberOfLines={1} style={styles.statValue}>
                    {item.value}
                  </AppText>
                  {item.sub ? <AppText style={styles.statSub}>{item.sub}</AppText> : null}
                </View>
              </View>
            ))}
          </View>
        </View>
      ))}

      <Pressable
        onPress={() => push("/stats/details")}
        style={({ pressed }) => [styles.goDeeperButton, featureShadows.md, pressed ? styles.pressedWide : null]}
      >
        <MaterialCommunityIcons color="#FFFFFF" name="star-four-points" size={16} />
        <AppText style={styles.goDeeperLabel}>Go deeper</AppText>
      </Pressable>
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
    paddingBottom: 40
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    marginBottom: 24
  },
  headerTitle: {
    ...featureTypography.title
  },
  section: {
    marginBottom: 32
  },
  sectionLabel: {
    ...featureTypography.microUpper,
    marginBottom: 12,
    paddingHorizontal: 4
  },
  sectionCards: {
    gap: 10
  },
  statCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    padding: 16,
    borderRadius: 18,
    backgroundColor: "#FFFFFF"
  },
  statIconShell: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center"
  },
  statCopy: {
    flex: 1
  },
  statLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 11,
    lineHeight: 14,
    textTransform: "uppercase",
    color: featurePalette.muted,
    marginBottom: 2
  },
  statValue: {
    fontFamily: "Manrope_700Bold",
    fontSize: 18,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  statSub: {
    ...featureTypography.label,
    marginTop: 2
  },
  goDeeperButton: {
    height: 52,
    borderRadius: 999,
    backgroundColor: featurePalette.foreground,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8
  },
  goDeeperLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 15,
    lineHeight: 20,
    color: "#FFFFFF"
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
  function push(href: string) {
    router.push(href as Href);
  }
