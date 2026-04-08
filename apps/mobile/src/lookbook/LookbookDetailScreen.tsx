import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { AppText } from "../ui";
import { CLOSET_ITEMS } from "../lib/reference/wardrobe";
import { featurePalette, featureTypography } from "../theme/feature";

export default function LookbookDetailScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [liked, setLiked] = useState(false);
  const numericId = Number(id ?? 1);

  const entry = useMemo(
    () => ({
      id: numericId,
      image: CLOSET_ITEMS[(numericId - 1 + CLOSET_ITEMS.length) % CLOSET_ITEMS.length]?.image,
      context: "Coffee with friends",
      date: "April 5, 2026",
      notes:
        "Felt effortless and put-together. The cream cardigan was the perfect layer for the mild weather.",
      items: CLOSET_ITEMS.slice(0, 3)
    }),
    [numericId]
  );

  function push(href: string) {
    router.push(href as Href);
  }

  return (
    <View style={styles.screen}>
      <View style={styles.hero}>
        <Image contentFit="cover" source={entry.image} style={styles.heroImage} />
        <View style={styles.heroTopRow}>
          <Pressable onPress={() => router.back()} style={styles.heroButton}>
            <Feather color={featurePalette.foreground} name="arrow-left" size={18} />
          </Pressable>
          <View style={styles.heroActions}>
            <Pressable onPress={() => setLiked((current) => !current)} style={styles.heroButton}>
              <Feather
                color={liked ? featurePalette.coral : featurePalette.foreground}
                name="heart"
                size={18}
              />
            </Pressable>
            <Pressable style={styles.heroButton}>
              <Feather color={featurePalette.foreground} name="share-2" size={18} />
            </Pressable>
          </View>
        </View>
      </View>

      <ScrollView
        bounces={false}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.titleBlock}>
          <AppText style={styles.title}>{entry.context}</AppText>
          <View style={styles.metaRow}>
            <View style={styles.metaItem}>
              <Feather color={featurePalette.muted} name="calendar" size={14} />
              <AppText style={styles.metaLabel}>{entry.date}</AppText>
            </View>
            <View style={styles.metaItem}>
              <Feather color={featurePalette.muted} name="tag" size={14} />
              <AppText style={styles.metaLabel}>{entry.items.length} items</AppText>
            </View>
          </View>
        </View>

        <View style={styles.noteBlock}>
          <AppText style={styles.noteCopy}>"{entry.notes}"</AppText>
        </View>

        <View style={styles.itemsBlock}>
          <AppText style={styles.sectionLabel}>Items worn</AppText>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            <View style={styles.itemsRow}>
              {entry.items.map((item) => (
                <Pressable
                  key={item.id}
                  onPress={() => push(`/closet/${item.id}`)}
                  style={styles.itemCard}
                >
                  <View style={styles.itemImageFrame}>
                    <Image contentFit="cover" source={item.image} style={styles.itemImage} />
                  </View>
                  <AppText numberOfLines={1} style={styles.itemLabel}>
                    {item.title}
                  </AppText>
                </Pressable>
              ))}
            </View>
          </ScrollView>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
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
  heroTopRow: {
    position: "absolute",
    top: 56,
    left: 20,
    right: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  heroActions: {
    flexDirection: "row",
    gap: 8
  },
  heroButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.8)",
    alignItems: "center",
    justifyContent: "center"
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 32
  },
  titleBlock: {
    marginBottom: 20
  },
  title: {
    ...featureTypography.title
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    marginTop: 8
  },
  metaItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6
  },
  metaLabel: {
    ...featureTypography.label,
    fontSize: 13,
    lineHeight: 18
  },
  noteBlock: {
    marginBottom: 24
  },
  noteCopy: {
    ...featureTypography.body,
    fontStyle: "italic"
  },
  itemsBlock: {
    gap: 12
  },
  sectionLabel: {
    ...featureTypography.microUpper
  },
  itemsRow: {
    flexDirection: "row",
    gap: 12
  },
  itemCard: {
    width: 100
  },
  itemImageFrame: {
    aspectRatio: 1,
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 6
  },
  itemImage: {
    width: "100%",
    height: "100%"
  },
  itemLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  }
});
