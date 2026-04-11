import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { router, type Href } from "expo-router";
import { useMemo, type ReactNode } from "react";
import { ScrollView, Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../auth/provider";
import { useClosetInsights, useClosetItemUsageIndex } from "../closet/insights";
import { useInsightOverview } from "../home/overview";
import { humanizeEnum } from "../lib/format";
import { AppText } from "../ui";
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
  const { session } = useAuth();
  const closetInsights = useClosetInsights(session?.access_token);
  const overview = useInsightOverview(session?.access_token);
  const mostWornIndex = useClosetItemUsageIndex(session?.access_token, { sort: "most_worn", maxItems: 40 });
  const leastWornIndex = useClosetItemUsageIndex(session?.access_token, { sort: "least_worn", maxItems: 40 });
  const mostWorn = mostWornIndex.snapshot.items[0] ?? null;
  const leastWorn = leastWornIndex.snapshot.items[0] ?? null;
  const topBrand = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of closetInsights.items) {
      if (!item.brand) {
        continue;
      }
      counts.set(item.brand, (counts.get(item.brand) ?? 0) + 1);
    }
    return Array.from(counts.entries()).sort((left, right) => right[1] - left[1])[0] ?? null;
  }, [closetInsights.items]);

  const totalWearLogs = overview.data?.all_time.total_wear_logs ?? 0;
  const streak = overview.data?.streaks.current_streak_days ?? 0;
  const longestStreak = overview.data?.streaks.longest_streak_days ?? 0;
  const activeCoverageRatio = overview.data?.current_month.active_closet_coverage_ratio ?? 0;
  const averageOutfitsPerWeek =
    totalWearLogs > 0 ? Math.round(((overview.data?.current_month.total_wear_logs ?? 0) / 4) * 10) / 10 : 0;

  const sections: Array<{ title: string; items: StatItem[] }> = [
    {
      title: "Overview",
      items: [
        {
          icon: <MaterialCommunityIcons color={featurePalette.foreground} name="hanger" size={20} />,
          label: "Outfits Logged",
          value: `${totalWearLogs}`,
          sub: "from confirmed wear logs",
          color: featurePalette.sage
        },
        {
          icon: <MaterialCommunityIcons color={featurePalette.coral} name="fire" size={20} />,
          label: "Current Streak",
          value: `${streak} days`,
          sub: `your best: ${longestStreak} days`,
          color: "rgba(255, 107, 107, 0.15)"
        },
        {
          icon: <Feather color={featurePalette.foreground} name="trending-up" size={20} />,
          label: "Avg. Outfits / Week",
          value: `${averageOutfitsPerWeek}`,
          sub: "based on this month",
          color: "rgba(216, 235, 207, 0.2)"
        },
        {
          icon: <Feather color="#7BA2FF" name="calendar" size={20} />,
          label: "Unique Items Worn",
          value: `${overview.data?.all_time.unique_items_worn ?? 0}`,
          sub: "across all confirmed wear logs",
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
          value: `${closetInsights.insights.totalItems}`,
          sub: "in your closet",
          color: "rgba(232, 219, 255, 0.3)"
        },
        {
          icon: <MaterialCommunityIcons color={featurePalette.foreground} name="chart-bar" size={20} />,
          label: "Top Category",
          value: closetInsights.insights.topCategory ? humanizeEnum(closetInsights.insights.topCategory.label) : "—",
          sub: closetInsights.insights.topCategory ? `${closetInsights.insights.topCategory.count} items` : "",
          color: featurePalette.secondary
        },
        {
          icon: <MaterialCommunityIcons color="#C78B00" name="palette-outline" size={20} />,
          label: "Most Common Color",
          value: closetInsights.insights.topColor ? humanizeEnum(closetInsights.insights.topColor.label) : "—",
          sub: closetInsights.insights.topColor ? `${closetInsights.insights.topColor.count} items` : "",
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
          sub: mostWorn ? `${mostWorn.wear_count} times · ${humanizeEnum(mostWorn.category)}` : "",
          color: "rgba(255, 239, 161, 0.2)"
        },
        {
          icon: <Feather color={featurePalette.muted} name="clock" size={20} />,
          label: "Least Worn Item",
          value: leastWorn?.title ?? "—",
          sub: leastWorn ? `${leastWorn.wear_count} times · ${humanizeEnum(leastWorn.category)}` : "",
          color: featurePalette.secondary
        },
        {
          icon: <Feather color="#FFB3C4" name="heart" size={20} />,
          label: "Coverage",
          value: `${Math.round(activeCoverageRatio * 100)}%`,
          sub: "active closet worn this month",
          color: "rgba(255, 234, 242, 0.35)"
        },
        {
          icon: <Feather color="#C78B00" name="sun" size={20} />,
          label: "Never Worn",
          value: `${overview.data?.all_time.never_worn_item_count ?? 0}`,
          sub: "confirmed closet items still untouched",
          color: "rgba(255, 239, 161, 0.15)"
        },
        {
          icon: <Feather color="#7658C3" name="moon" size={20} />,
          label: "Worn This Month",
          value: `${overview.data?.current_month.unique_items_worn ?? 0}`,
          sub: "unique closet items this month",
          color: "rgba(232, 219, 255, 0.2)"
        },
        {
          icon: <MaterialCommunityIcons color="#567848" name="star-four-points" size={20} />,
          label: "Processed Closet",
          value: `${Math.round(
            closetInsights.insights.totalItems === 0
              ? 0
              : (closetInsights.insights.processedItems / closetInsights.insights.totalItems) * 100
          )}%`,
          sub: "items with polished imagery",
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
