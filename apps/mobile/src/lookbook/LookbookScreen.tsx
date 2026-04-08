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
import { LOOKBOOK_ENTRIES, LOOKBOOK_TABS } from "../lib/reference/wardrobe";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";

export default function LookbookScreen() {
  const [activeTab, setActiveTab] = useState<(typeof LOOKBOOK_TABS)[number]>("All");

  function push(href: string) {
    router.push(href as Href);
  }

  const filteredEntries = useMemo(
    () =>
      LOOKBOOK_ENTRIES.filter((entry) => {
        if (activeTab === "All") {
          return true;
        }
        if (activeTab === "Favorites") {
          return entry.type === "outfit";
        }
        return entry.type === "inspiration";
      }),
    [activeTab]
  );

  return (
    <ScrollView
      bounces={false}
      contentContainerStyle={styles.content}
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
        <AppText style={styles.subtitle}>The ones you&apos;ll want to wear again</AppText>
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

      {filteredEntries.length > 0 ? (
        <View style={styles.grid}>
          {filteredEntries.map((entry) => (
            <Pressable
              key={entry.id}
              onPress={() => push(`/lookbook/${entry.id}`)}
              style={({ pressed }) => [styles.gridItem, pressed ? styles.pressedWide : null]}
            >
              <View style={styles.gridImageFrame}>
                <Image contentFit="cover" source={entry.image} style={styles.gridImage} />
                {entry.type === "inspiration" ? (
                  <View style={styles.sparkleBadge}>
                    <MaterialCommunityIcons color={featurePalette.foreground} name="star-four-points" size={12} />
                  </View>
                ) : null}
              </View>
              <AppText style={styles.gridTitle}>{entry.context}</AppText>
              <AppText style={styles.gridMeta}>
                {entry.date}
                {entry.items > 0 ? ` · ${entry.items} items` : ""}
              </AppText>
            </Pressable>
          ))}
        </View>
      ) : (
        <View style={styles.emptyState}>
          <View style={styles.emptyIcon}>
            <Feather color={featurePalette.muted} name="camera" size={24} />
          </View>
          <AppText style={styles.emptyTitle}>Nothing here yet</AppText>
          <AppText style={styles.emptySubtitle}>Start capturing your looks</AppText>
        </View>
      )}
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
    marginTop: 4
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
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 8,
    position: "relative"
  },
  gridImage: {
    width: "100%",
    height: "100%"
  },
  sparkleBadge: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.8)",
    alignItems: "center",
    justifyContent: "center"
  },
  gridTitle: {
    fontFamily: "Manrope_500Medium",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  gridMeta: {
    ...featureTypography.label,
    marginTop: 2
  },
  emptyState: {
    alignItems: "center",
    justifyContent: "center",
    paddingTop: 96
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
    color: featurePalette.muted
  },
  emptySubtitle: {
    ...featureTypography.label,
    marginTop: 2
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
