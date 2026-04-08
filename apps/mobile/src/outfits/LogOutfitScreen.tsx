import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams, type Href } from "expo-router";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import {
  Animated,
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useOutfits } from "../outfits/provider";
import { AppText } from "../ui";
import { CLOSET_ITEMS, CATEGORY_LABELS, type ClosetItem, formatProfileReviewDate } from "../lib/reference/wardrobe";
import { GlassIconButton, PrimaryActionButton } from "../ui/feature-components";
import { launchCameraForSingleImage } from "../media/picker";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";

type LogStep = "processing" | "closet" | "review" | "success";

function pickRandomItems(count: number) {
  return [...CLOSET_ITEMS].sort(() => Math.random() - 0.5).slice(0, count);
}

export default function LogOutfitScreen() {
  const { mode } = useLocalSearchParams<{ mode?: string }>();
  const { consumeLogOutfitPhotoUri, upsertOutfit } = useOutfits();
  const [step, setStep] = useState<LogStep>(
    mode === "photo" ? "processing" : "closet"
  );
  const [selectedItems, setSelectedItems] = useState<ClosetItem[]>([]);
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const autoTriggered = useRef(false);

  useEffect(() => {
    if (mode !== "photo" || autoTriggered.current) {
      return;
    }

    autoTriggered.current = true;
    const storedUri = consumeLogOutfitPhotoUri();
    if (!storedUri) {
      setStep("closet");
      return;
    }

    setPhotoUri(storedUri);
    setStep("processing");

    const timer = setTimeout(() => {
      setSelectedItems(pickRandomItems(3));
      setStep("review");
    }, 2400);

    return () => {
      clearTimeout(timer);
    };
  }, [consumeLogOutfitPhotoUri, mode]);

  const handleManualPhoto = useCallback(async () => {
    const uri = await launchCameraForSingleImage();
    if (!uri) {
      return;
    }

    setPhotoUri(uri);
    setStep("processing");

    setTimeout(() => {
      setSelectedItems(pickRandomItems(3));
      setStep("review");
    }, 2400);
  }, []);

  const handleConfirm = useCallback(() => {
    const today = new Date();
    upsertOutfit(today.toISOString().split("T")[0] ?? "", {
      image: selectedItems[0]?.image ?? null,
      imageUri: photoUri,
      items: selectedItems,
      note: undefined
    });
    setStep("success");
  }, [photoUri, selectedItems, upsertOutfit]);

  const handleBack = useCallback(() => {
    if (step === "closet" || step === "processing") {
      router.back();
      return;
    }

    if (step === "review") {
      setStep("closet");
      return;
    }

    router.back();
  }, [step]);

  if (step === "processing") {
    return <LogOutfitProcessing imageUri={photoUri} onFallbackPhoto={handleManualPhoto} />;
  }

  if (step === "closet") {
    return (
      <LogOutfitClosetPick
        initialItems={selectedItems}
        onBack={handleBack}
        onConfirm={(items) => {
          setSelectedItems(items);
          setStep("review");
        }}
      />
    );
  }

  if (step === "review") {
    return (
      <LogOutfitReview
        items={selectedItems}
        onBack={handleBack}
        onConfirm={handleConfirm}
        onRemoveItem={(id) => {
          setSelectedItems((current) => current.filter((item) => item.id !== id));
        }}
      />
    );
  }

  return <LogOutfitSuccess onDone={() => router.push("/" as Href)} />;
}

function LogOutfitProcessing({
  imageUri,
  onFallbackPhoto
}: {
  imageUri: string | null;
  onFallbackPhoto: () => void | Promise<void>;
}) {
  const rotation = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(rotation, {
        toValue: 1,
        duration: 1800,
        useNativeDriver: true
      })
    );

    loop.start();
    return () => {
      loop.stop();
    };
  }, [rotation]);

  return (
    <SafeAreaView style={styles.processingScreen}>
      <View style={StyleSheet.absoluteFillObject}>
        {imageUri ? (
          <Image contentFit="cover" source={{ uri: imageUri }} style={StyleSheet.absoluteFillObject} />
        ) : null}
        <View style={styles.processingBackdrop} />
      </View>

      <View style={styles.processingBody}>
        {!imageUri ? (
          <Pressable onPress={() => void onFallbackPhoto()} style={styles.processingFallback}>
            <Feather color={featurePalette.darkText} name="camera" size={18} />
            <AppText style={styles.processingFallbackLabel}>Take a photo</AppText>
          </Pressable>
        ) : null}

        <View style={styles.processingSpinnerShell}>
          <Animated.View
            style={[
              styles.processingSpinner,
              {
                transform: [
                  {
                    rotate: rotation.interpolate({
                      inputRange: [0, 1],
                      outputRange: ["0deg", "360deg"]
                    })
                  }
                ]
              }
            ]}
          />
          <View style={[styles.processingSpinnerCore, featureShadows.md]}>
            <View style={styles.processingCoreDot} />
          </View>
        </View>

        <AppText style={styles.processingTitle}>Analyzing your outfit…</AppText>
        <AppText style={styles.processingSubtitle}>Detecting items and colors</AppText>
      </View>
    </SafeAreaView>
  );
}

function LogOutfitClosetPick({
  initialItems,
  onBack,
  onConfirm
}: {
  initialItems: ClosetItem[];
  onBack: () => void;
  onConfirm: (items: ClosetItem[]) => void;
}) {
  const [activeCategory, setActiveCategory] = useState("all");
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(initialItems.map((item) => item.id))
  );

  const categories = useMemo(() => ["all", ...Object.keys(CATEGORY_LABELS)], []);
  const filtered = useMemo(
    () =>
      activeCategory === "all"
        ? CLOSET_ITEMS
        : CLOSET_ITEMS.filter((item) => item.category === activeCategory),
    [activeCategory]
  );

  function toggle(id: number) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < 6) {
        next.add(id);
      }

      return next;
    });
  }

  return (
    <SafeAreaView style={styles.flowScreen}>
      <View style={styles.flowHeader}>
        <GlassIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
          onPress={onBack}
        />
        <AppText style={styles.flowHeaderTitle}>Select Items</AppText>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        bounces={false}
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.categoryRow}
      >
        {categories.map((category) => {
          const active = category === activeCategory;

          return (
            <Pressable
              key={category}
              onPress={() => setActiveCategory(category)}
              style={[
                styles.categoryChip,
                active ? styles.categoryChipActive : null
              ]}
            >
              <AppText
                style={[
                  styles.categoryChipLabel,
                  active ? styles.categoryChipLabelActive : null
                ]}
              >
                {category === "all" ? "All" : CATEGORY_LABELS[category]}
              </AppText>
            </Pressable>
          );
        })}
      </ScrollView>

      <ScrollView
        bounces={false}
        contentContainerStyle={styles.closetGrid}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.tileGrid}>
          {filtered.map((item) => {
            const isSelected = selected.has(item.id);

            return (
              <Pressable
                key={item.id}
                onPress={() => toggle(item.id)}
                style={[
                  styles.closetTile,
                  isSelected ? styles.closetTileSelected : null
                ]}
              >
                <Image contentFit="cover" source={item.image} style={styles.closetTileImage} />
                {isSelected ? (
                  <View style={styles.closetSelectionOverlay}>
                    <View style={styles.closetSelectionBadge}>
                      <Feather color="#FFFFFF" name="check" size={14} />
                    </View>
                  </View>
                ) : null}
                <View style={styles.closetTileLabelGradient}>
                  <AppText numberOfLines={2} style={styles.closetTileLabel}>
                    {item.title}
                  </AppText>
                </View>
              </Pressable>
            );
          })}
        </View>
      </ScrollView>

      {selected.size > 0 ? (
        <View style={styles.bottomCtaShell}>
          <PrimaryActionButton
            label={`Continue with ${selected.size} ${selected.size === 1 ? "item" : "items"}`}
            onPress={() => {
              onConfirm(CLOSET_ITEMS.filter((item) => selected.has(item.id)));
            }}
          />
        </View>
      ) : null}
    </SafeAreaView>
  );
}

function LogOutfitReview({
  items,
  onBack,
  onConfirm,
  onRemoveItem
}: {
  items: ClosetItem[];
  onBack: () => void;
  onConfirm: () => void;
  onRemoveItem: (id: number) => void;
}) {
  return (
    <SafeAreaView style={styles.flowScreen}>
      <View style={styles.flowHeader}>
        <GlassIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
          onPress={onBack}
        />
        <AppText style={styles.flowHeaderTitle}>Review Outfit</AppText>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        bounces={false}
        contentContainerStyle={styles.reviewContent}
        showsVerticalScrollIndicator={false}
      >
        <AppText style={styles.reviewDate}>{formatProfileReviewDate(new Date())}</AppText>

        <View style={styles.reviewList}>
          {items.map((item) => (
            <View key={item.id} style={[styles.reviewCard, featureShadows.sm]}>
              <Image contentFit="cover" source={item.image} style={styles.reviewCardImage} />
              <View style={styles.reviewCardCopy}>
                <AppText numberOfLines={1} style={styles.reviewCardTitle}>
                  {item.title}
                </AppText>
                <AppText style={styles.reviewCardSubtitle}>
                  {item.color} · {item.type}
                </AppText>
              </View>
              <Pressable onPress={() => onRemoveItem(item.id)} style={styles.reviewRemoveButton}>
                <Feather color={featurePalette.muted} name="x" size={16} />
              </Pressable>
            </View>
          ))}
        </View>

        {items.length > 1 ? (
          <View style={styles.reviewPreviewSection}>
            <AppText style={styles.reviewPreviewLabel}>Your outfit</AppText>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.reviewPreviewRow}>
                {items.map((item) => (
                  <View key={item.id} style={[styles.reviewPreviewCard, featureShadows.sm]}>
                    <Image contentFit="cover" source={item.image} style={styles.reviewPreviewImage} />
                  </View>
                ))}
              </View>
            </ScrollView>
          </View>
        ) : null}
      </ScrollView>

      <View style={styles.bottomCtaShell}>
        <PrimaryActionButton
          disabled={items.length === 0}
          label="Log Outfit"
          onPress={onConfirm}
        />
      </View>
    </SafeAreaView>
  );
}

function LogOutfitSuccess({ onDone }: { onDone: () => void }) {
  const [showToast, setShowToast] = useState(false);
  const scale = useRef(new Animated.Value(0)).current;
  const titleOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.spring(scale, {
      toValue: 1,
      damping: 12,
      mass: 0.9,
      stiffness: 200,
      useNativeDriver: true
    }).start();

    Animated.timing(titleOpacity, {
      toValue: 1,
      duration: 320,
      useNativeDriver: true
    }).start();

    const toastTimer = setTimeout(() => {
      setShowToast(true);
    }, 1200);
    const doneTimer = setTimeout(onDone, 2600);

    return () => {
      clearTimeout(doneTimer);
      clearTimeout(toastTimer);
    };
  }, [onDone, scale, titleOpacity]);

  return (
    <SafeAreaView style={styles.successScreen}>
      <Animated.View style={[styles.successCircleShell, { transform: [{ scale }] }]}>
        <View style={styles.successGlow} />
        <View style={styles.successCircle}>
          <Feather color={featurePalette.foreground} name="check" size={36} />
        </View>
      </Animated.View>

      <Animated.View style={{ opacity: titleOpacity }}>
        <AppText style={styles.successTitle}>Outfit logged ✨</AppText>
        <AppText style={styles.successSubtitle}>Your style story continues</AppText>
      </Animated.View>

      <View style={styles.successSyncRow}>
        {["Calendar", "Stats", "Closet"].map((label) => (
          <View key={label} style={styles.successSyncChip}>
            <AppText style={styles.successSyncLabel}>✓ {label}</AppText>
          </View>
        ))}
      </View>

      {showToast ? (
        <View style={[styles.syncToast, featureShadows.md]}>
          <AppText style={styles.syncToastTitle}>Profile updated</AppText>
          <AppText style={styles.syncToastDescription}>Calendar and stats synced ✨</AppText>
        </View>
      ) : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  processingScreen: {
    flex: 1,
    backgroundColor: featurePalette.background,
    justifyContent: "center",
    alignItems: "center"
  },
  processingBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(250, 249, 247, 0.72)"
  },
  processingBody: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24
  },
  processingFallback: {
    position: "absolute",
    top: -80,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.92)",
    paddingHorizontal: 16,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  processingFallbackLabel: {
    ...featureTypography.bodyStrong,
    fontSize: 14
  },
  processingSpinnerShell: {
    width: 80,
    height: 80,
    marginBottom: 32,
    alignItems: "center",
    justifyContent: "center"
  },
  processingSpinner: {
    position: "absolute",
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 3,
    borderColor: "rgba(216, 235, 207, 0.2)",
    borderTopColor: featurePalette.sage,
    borderRightColor: featurePalette.sage
  },
  processingSpinnerCore: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  processingCoreDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: featurePalette.sage
  },
  processingTitle: {
    ...featureTypography.title,
    textAlign: "center",
    marginBottom: 8
  },
  processingSubtitle: {
    ...featureTypography.label,
    fontSize: 14,
    lineHeight: 20
  },
  flowScreen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  flowHeader: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  flowHeaderTitle: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 18,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  headerSpacer: {
    width: 40
  },
  categoryRow: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    gap: 8
  },
  categoryChip: {
    height: 36,
    borderRadius: 18,
    paddingHorizontal: 16,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  categoryChipActive: {
    backgroundColor: featurePalette.foreground
  },
  categoryChipLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  categoryChipLabelActive: {
    color: featurePalette.background
  },
  closetGrid: {
    flex: 1
  },
  tileGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: 20,
    paddingBottom: 140,
    gap: 10
  },
  closetTile: {
    width: "31%",
    aspectRatio: 3 / 4,
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    position: "relative"
  },
  closetTileSelected: {
    borderWidth: 2.5,
    borderColor: featurePalette.foreground
  },
  closetTileImage: {
    width: "100%",
    height: "100%"
  },
  closetSelectionOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(15, 23, 42, 0.08)",
    paddingTop: 8,
    paddingRight: 8,
    alignItems: "flex-end"
  },
  closetSelectionBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: featurePalette.foreground,
    alignItems: "center",
    justifyContent: "center"
  },
  closetTileLabelGradient: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: 10,
    paddingTop: 24,
    paddingBottom: 10,
    backgroundColor: "rgba(0,0,0,0.28)"
  },
  closetTileLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 11,
    lineHeight: 14,
    color: "#FFFFFF"
  },
  bottomCtaShell: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 24,
    backgroundColor: "rgba(250,249,247,0.94)"
  },
  reviewContent: {
    paddingHorizontal: 24,
    paddingBottom: 132
  },
  reviewDate: {
    ...featureTypography.microUpper,
    marginTop: 20,
    marginBottom: 20
  },
  reviewList: {
    gap: 12
  },
  reviewCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 12,
    paddingRight: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 16
  },
  reviewCardImage: {
    width: 64,
    height: 80,
    borderRadius: 14
  },
  reviewCardCopy: {
    flex: 1
  },
  reviewCardTitle: {
    ...featureTypography.bodyStrong
  },
  reviewCardSubtitle: {
    ...featureTypography.label,
    marginTop: 2
  },
  reviewRemoveButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  reviewPreviewSection: {
    marginTop: 28
  },
  reviewPreviewLabel: {
    ...featureTypography.microUpper,
    marginBottom: 12
  },
  reviewPreviewRow: {
    flexDirection: "row",
    gap: 8
  },
  reviewPreviewCard: {
    width: 64,
    height: 80,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  reviewPreviewImage: {
    width: "100%",
    height: "100%"
  },
  successScreen: {
    flex: 1,
    backgroundColor: featurePalette.background,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24
  },
  successCircleShell: {
    marginBottom: 24,
    alignItems: "center",
    justifyContent: "center"
  },
  successGlow: {
    position: "absolute",
    width: 160,
    height: 160,
    borderRadius: 80,
    backgroundColor: "rgba(216, 235, 207, 0.45)"
  },
  successCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: featurePalette.sage,
    alignItems: "center",
    justifyContent: "center"
  },
  successTitle: {
    ...featureTypography.display,
    fontSize: 28,
    lineHeight: 32,
    textAlign: "center",
    marginBottom: 8
  },
  successSubtitle: {
    ...featureTypography.label,
    fontSize: 14,
    lineHeight: 18,
    textAlign: "center"
  },
  successSyncRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 28
  },
  successSyncChip: {
    backgroundColor: "#F0FDF4",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4
  },
  successSyncLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.success
  },
  syncToast: {
    position: "absolute",
    bottom: 36,
    left: 24,
    right: 24,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 14
  },
  syncToastTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.darkText,
    marginBottom: 2
  },
  syncToastDescription: {
    ...featureTypography.label,
    fontSize: 13,
    lineHeight: 18
  }
});
