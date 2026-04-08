import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { useOutfits } from "../outfits/provider";
import { AppText } from "../ui";
import {
  CLOSET_ITEMS,
  type ClosetItem,
  formatFullDate,
  parseDateKey
} from "../lib/reference/wardrobe";
import {
  FeatureSheet,
  FeatureTextArea,
  GlassIconButton,
  PrimaryActionButton
} from "../ui/feature-components";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";

export default function EditOutfitScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { outfits, upsertOutfit } = useOutfits();
  const outfit = id ? outfits[id] : undefined;

  const [items, setItems] = useState<ClosetItem[]>(outfit?.items ?? []);
  const [note, setNote] = useState(outfit?.note ?? "");
  const [showPicker, setShowPicker] = useState(false);
  const [removedItem, setRemovedItem] = useState<ClosetItem | null>(null);
  const [showUndo, setShowUndo] = useState(false);

  const parsedDate = useMemo(() => parseDateKey(id ?? ""), [id]);
  const availableItems = useMemo(
    () => CLOSET_ITEMS.filter((candidate) => !items.find((item) => item.id === candidate.id)),
    [items]
  );

  useEffect(() => {
    if (!showUndo) {
      return;
    }

    const timer = setTimeout(() => {
      setShowUndo(false);
    }, 3000);

    return () => {
      clearTimeout(timer);
    };
  }, [showUndo]);

  if (!id || !outfit) {
    return (
      <View style={styles.emptyState}>
        <AppText style={styles.emptyStateEmoji}>🤷</AppText>
        <AppText style={styles.emptyStateTitle}>No outfit found</AppText>
        <AppText style={styles.emptyStateCopy}>There&apos;s nothing to edit for this date</AppText>
        <Pressable onPress={() => router.back()} style={styles.emptyStateButton}>
          <AppText style={styles.emptyStateButtonLabel}>Go Back</AppText>
        </Pressable>
      </View>
    );
  }

  const outfitId = id;
  const outfitEntry = outfit;

  function handleRemove(item: ClosetItem) {
    setRemovedItem(item);
    setItems((current) => current.filter((candidate) => candidate.id !== item.id));
    setShowUndo(true);
  }

  function handleUndo() {
    if (!removedItem) {
      return;
    }

    setItems((current) => [...current, removedItem]);
    setRemovedItem(null);
    setShowUndo(false);
  }

  function handleSave() {
    upsertOutfit(outfitId, {
      image: items[0]?.image ?? outfitEntry.image ?? null,
      imageUri: outfitEntry.imageUri,
      items,
      note,
      occasion: outfitEntry.occasion
    });
    router.back();
  }

  return (
    <>
      <ScrollView
        bounces={false}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        style={styles.screen}
      >
        <View style={styles.header}>
          <GlassIconButton
            icon={<Feather color={featurePalette.darkText} name="arrow-left" size={18} />}
            onPress={() => router.back()}
          />
          <AppText style={styles.headerTitle}>Edit Outfit</AppText>
          <Pressable
            onPress={handleSave}
            style={({ pressed }) => [styles.headerSave, pressed ? styles.pressed : null]}
          >
            <Feather color="#FFFFFF" name="check" size={18} />
          </Pressable>
        </View>

        <View style={styles.dateWrapper}>
          <View style={[styles.datePill, featureShadows.sm]}>
            <Feather color={featurePalette.warmGray} name="calendar" size={16} />
            <AppText style={styles.datePillLabel}>{formatFullDate(parsedDate)}</AppText>
            <Feather color={featurePalette.muted} name="chevron-down" size={14} />
          </View>
        </View>

        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <AppText style={styles.sectionLabel}>Items · {items.length}</AppText>
            <Pressable onPress={() => setShowPicker(true)} style={styles.inlineAction}>
              <Feather color={featurePalette.coral} name="plus" size={14} />
              <AppText style={styles.inlineActionLabel}>Add item</AppText>
            </Pressable>
          </View>

          <View style={styles.itemList}>
            {items.map((item) => (
              <View key={item.id} style={[styles.itemRow, featureShadows.sm]}>
                <Image contentFit="cover" source={item.image} style={styles.itemRowImage} />
                <View style={styles.itemRowCopy}>
                  <AppText numberOfLines={1} style={styles.itemRowTitle}>
                    {item.title}
                  </AppText>
                  <AppText style={styles.itemRowSubtitle}>{item.brand}</AppText>
                </View>
                <Pressable onPress={() => handleRemove(item)} style={styles.removeButton}>
                  <Feather color={featurePalette.danger} name="x" size={14} />
                </Pressable>
              </View>
            ))}
          </View>
        </View>

        <View style={styles.section}>
          <AppText style={styles.sectionLabel}>Note</AppText>
          <FeatureTextArea
            onChangeText={setNote}
            placeholder="Add a note…"
            value={note}
          />
        </View>

        <PrimaryActionButton label="Save Changes" onPress={handleSave} icon={<Feather color="#FFFFFF" name="check" size={16} />} />
      </ScrollView>

      {showUndo ? (
        <View style={[styles.undoToast, featureShadows.lg]}>
          <AppText style={styles.undoLabel}>Item removed</AppText>
          <Pressable onPress={handleUndo}>
            <AppText style={styles.undoAction}>Undo</AppText>
          </Pressable>
        </View>
      ) : null}

      <FeatureSheet
        onClose={() => setShowPicker(false)}
        title="Add Item"
        visible={showPicker}
      >
        <View style={styles.pickerGrid}>
          {availableItems.map((item) => (
            <Pressable
              key={item.id}
              onPress={() => {
                setItems((current) => [...current, item]);
                setShowPicker(false);
              }}
              style={({ pressed }) => [styles.pickerItem, pressed ? styles.pressedWide : null]}
            >
              <View style={[styles.pickerImageFrame, featureShadows.sm]}>
                <Image contentFit="cover" source={item.image} style={styles.pickerImage} />
              </View>
              <AppText numberOfLines={1} style={styles.pickerLabel}>
                {item.title}
              </AppText>
            </Pressable>
          ))}
        </View>
      </FeatureSheet>
    </>
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
    paddingBottom: 36,
    gap: 24
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  headerTitle: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 17,
    lineHeight: 22,
    color: featurePalette.darkText
  },
  headerSave: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: featurePalette.success
  },
  dateWrapper: {
    paddingHorizontal: 4
  },
  datePill: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    borderRadius: 999,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 12
  },
  datePillLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.darkText
  },
  section: {
    gap: 12
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  sectionLabel: {
    ...featureTypography.microUpper
  },
  inlineAction: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6
  },
  inlineActionLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.coral
  },
  itemList: {
    gap: 12
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 12
  },
  itemRowImage: {
    width: 56,
    height: 70,
    borderRadius: 10
  },
  itemRowCopy: {
    flex: 1
  },
  itemRowTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.darkText
  },
  itemRowSubtitle: {
    ...featureTypography.label,
    marginTop: 2
  },
  removeButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FEE2E2"
  },
  undoToast: {
    position: "absolute",
    left: 24,
    right: 24,
    bottom: 32,
    borderRadius: 999,
    backgroundColor: featurePalette.darkText,
    paddingHorizontal: 20,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  undoLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 13,
    lineHeight: 18,
    color: "#FFFFFF"
  },
  undoAction: {
    fontFamily: "Manrope_700Bold",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.coral
  },
  pickerGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    paddingBottom: 8
  },
  pickerItem: {
    width: "30.5%"
  },
  pickerImageFrame: {
    aspectRatio: 3 / 4,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 6
  },
  pickerImage: {
    width: "100%",
    height: "100%"
  },
  pickerLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.darkText
  },
  emptyState: {
    flex: 1,
    backgroundColor: featurePalette.background,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32
  },
  emptyStateEmoji: {
    fontSize: 48,
    lineHeight: 52,
    marginBottom: 16
  },
  emptyStateTitle: {
    ...featureTypography.title,
    textAlign: "center",
    marginBottom: 8
  },
  emptyStateCopy: {
    ...featureTypography.body,
    textAlign: "center",
    marginBottom: 24
  },
  emptyStateButton: {
    height: 48,
    borderRadius: 24,
    paddingHorizontal: 28,
    backgroundColor: featurePalette.darkText,
    alignItems: "center",
    justifyContent: "center"
  },
  emptyStateButtonLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: "#FFFFFF"
  },
  pressed: {
    transform: [{ scale: 0.95 }]
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
