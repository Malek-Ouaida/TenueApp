import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams, type Href } from "expo-router";
import type { ImagePickerAsset } from "expo-image-picker";
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

import { useAuth } from "../auth/provider";
import { useConfirmedClosetBrowse } from "../closet/hooks";
import {
  prepareUploadAsset,
  selectSingleImage,
  uploadFileToPresignedUrl
} from "../closet/upload";
import { humanizeEnum } from "../lib/format";
import { formatProfileReviewDate } from "../lib/reference/wardrobe";
import { useOutfits } from "../outfits/provider";
import { AppText } from "../ui";
import { GlassIconButton, PrimaryActionButton } from "../ui/feature-components";
import { supportsNativeAnimatedDriver } from "../lib/runtime";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";
import { completeWearUpload, createWearLog, createWearUploadIntent } from "../wear/client";
import { formatLocalDate, getLocalTimeZone } from "../wear/dates";
import type { WearItemRoleValue } from "../wear/types";

type LogStep = "processing" | "closet" | "review";

type ClosetSelectionItem = {
  id: string;
  title: string | null;
  category: string | null;
  subcategory: string | null;
  primaryColor: string | null;
  imageUri: string | null;
  thumbnailUri: string | null;
};

function mapCategoryToWearRole(category: string | null | undefined): WearItemRoleValue {
  switch (category) {
    case "top":
    case "tops":
      return "top";
    case "bottom":
    case "bottoms":
      return "bottom";
    case "dress":
    case "dresses":
      return "dress";
    case "outerwear":
      return "outerwear";
    case "shoes":
      return "shoes";
    case "bag":
    case "bags":
      return "bag";
    case "accessories":
    case "accessory":
      return "accessory";
    default:
      return "other";
  }
}

export default function LogOutfitScreen() {
  const { mode } = useLocalSearchParams<{ mode?: string }>();
  const { session } = useAuth();
  const { consumeLogOutfitPhotoAsset } = useOutfits();
  const closet = useConfirmedClosetBrowse(session?.access_token, { include_archived: false }, 100);
  const [step, setStep] = useState<LogStep>(
    mode === "photo" ? "processing" : "closet"
  );
  const [selectedItems, setSelectedItems] = useState<ClosetSelectionItem[]>([]);
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const autoTriggered = useRef(false);

  const closetItems = useMemo<ClosetSelectionItem[]>(
    () =>
      closet.items.map((item) => ({
        id: item.item_id,
        title: item.title,
        category: item.category,
        subcategory: item.subcategory,
        primaryColor: item.primary_color,
        imageUri: item.display_image?.url ?? item.thumbnail_image?.url ?? null,
        thumbnailUri: item.thumbnail_image?.url ?? item.display_image?.url ?? null
      })),
    [closet.items]
  );

  const processPhotoAsset = useCallback(
    async (asset: ImagePickerAsset) => {
      if (!session?.access_token) {
        setError("Sign in again to create a wear event.");
        return;
      }

      setPhotoUri(asset.uri ?? null);
      setStep("processing");
      setError(null);
      setIsSubmitting(true);

      try {
        const wearLog = await createWearLog(session.access_token, {
          mode: "photo_upload",
          wear_date: formatLocalDate(new Date()),
          worn_at: new Date().toISOString(),
          timezone_name: getLocalTimeZone()
        });
        const preparedAsset = await prepareUploadAsset(asset);
        const uploadIntent = await createWearUploadIntent(session.access_token, wearLog.id, {
          filename: preparedAsset.filename,
          mime_type: preparedAsset.mime_type,
          file_size: preparedAsset.file_size,
          sha256: preparedAsset.sha256
        });

        await uploadFileToPresignedUrl(preparedAsset, uploadIntent.upload);

        const completedWearLog = await completeWearUpload(
          session.access_token,
          wearLog.id,
          uploadIntent.upload_intent_id
        );

        router.replace(`/wear/${completedWearLog.id}` as Href);
      } catch (uploadError) {
        setError(uploadError instanceof Error ? uploadError.message : "Wear photo upload failed.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [session?.access_token]
  );

  useEffect(() => {
    if (mode !== "photo" || autoTriggered.current) {
      return;
    }

    autoTriggered.current = true;
    const storedAsset = consumeLogOutfitPhotoAsset();
    if (!storedAsset) {
      setError("Take a photo to start a wear event.");
      setIsSubmitting(false);
      return;
    }

    void processPhotoAsset(storedAsset);
  }, [consumeLogOutfitPhotoAsset, mode, processPhotoAsset]);

  const handleManualPhoto = useCallback(async () => {
    const asset = await selectSingleImage("camera");
    if (!asset) {
      return;
    }

    void processPhotoAsset(asset);
  }, [processPhotoAsset]);

  const handleConfirm = useCallback(async () => {
    if (!session?.access_token || selectedItems.length === 0) {
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const wearLog = await createWearLog(session.access_token, {
        mode: "manual_items",
        wear_date: formatLocalDate(new Date()),
        worn_at: new Date().toISOString(),
        timezone_name: getLocalTimeZone(),
        items: selectedItems.map((item, index) => ({
          closet_item_id: item.id,
          role: mapCategoryToWearRole(item.category),
          sort_index: index,
          source: "manual"
        }))
      });

      router.replace(`/wear/${wearLog.id}` as Href);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Wear log could not be created.");
    } finally {
      setIsSubmitting(false);
    }
  }, [selectedItems, session?.access_token]);

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
    return (
      <LogOutfitProcessing
        error={error}
        imageUri={photoUri}
        isWorking={isSubmitting}
        onFallbackPhoto={handleManualPhoto}
        onUseCloset={() => {
          setError(null);
          setStep("closet");
        }}
      />
    );
  }

  if (step === "closet") {
    return (
      <LogOutfitClosetPick
        error={closet.error}
        initialItems={selectedItems}
        isLoading={closet.isLoading}
        items={closetItems}
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
        error={error}
        items={selectedItems}
        isSubmitting={isSubmitting}
        onBack={handleBack}
        onConfirm={handleConfirm}
        onRemoveItem={(id) => {
          setSelectedItems((current) => current.filter((item) => item.id !== id));
        }}
      />
    );
  }

  return null;
}

function LogOutfitProcessing({
  error,
  imageUri,
  isWorking,
  onFallbackPhoto,
  onUseCloset
}: {
  error: string | null;
  imageUri: string | null;
  isWorking: boolean;
  onFallbackPhoto: () => void | Promise<void>;
  onUseCloset: () => void;
}) {
  const rotation = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!isWorking) {
      return;
    }

    const loop = Animated.loop(
      Animated.timing(rotation, {
        toValue: 1,
        duration: 1800,
        useNativeDriver: supportsNativeAnimatedDriver
      })
    );

    loop.start();
    return () => {
      loop.stop();
    };
  }, [isWorking, rotation]);

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

        {error ? (
          <View style={[styles.processingErrorCard, featureShadows.lg]}>
            <AppText style={styles.processingTitle}>Wear log could not start</AppText>
            <AppText style={styles.processingSubtitle}>{error}</AppText>
            <View style={styles.processingErrorActions}>
              <PrimaryActionButton
                label="Try Photo Again"
                onPress={() => void onFallbackPhoto()}
              />
              <Pressable onPress={onUseCloset} style={styles.processingSecondaryButton}>
                <AppText style={styles.processingSecondaryButtonLabel}>Pick from closet instead</AppText>
              </Pressable>
            </View>
          </View>
        ) : (
          <>
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
            <AppText style={styles.processingSubtitle}>
              Uploading the photo and preparing a wear event for review.
            </AppText>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

function LogOutfitClosetPick({
  error,
  initialItems,
  isLoading,
  items,
  onBack,
  onConfirm
}: {
  error: string | null;
  initialItems: ClosetSelectionItem[];
  isLoading: boolean;
  items: ClosetSelectionItem[];
  onBack: () => void;
  onConfirm: (items: ClosetSelectionItem[]) => void;
}) {
  const [activeCategory, setActiveCategory] = useState("all");
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(initialItems.map((item) => item.id))
  );

  const categories = useMemo(
    () => [
      "all",
      ...items
        .map((item) => item.category)
        .filter((value): value is string => Boolean(value))
        .filter((value, index, values) => values.indexOf(value) === index)
    ],
    [items]
  );

  const filtered = useMemo(
    () =>
      activeCategory === "all"
        ? items
        : items.filter((item) => item.category === activeCategory),
    [activeCategory, items]
  );

  function toggle(id: string) {
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
                {category === "all" ? "All" : humanizeEnum(category)}
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
        {error ? (
          <View style={styles.inlineNoticeCard}>
            <AppText style={styles.inlineNoticeTitle}>Closet could not load</AppText>
            <AppText style={styles.inlineNoticeBody}>{error}</AppText>
          </View>
        ) : null}

        {isLoading ? (
          <View style={styles.inlineNoticeCard}>
            <AppText style={styles.inlineNoticeTitle}>Loading your closet</AppText>
            <AppText style={styles.inlineNoticeBody}>Preparing confirmed items for wear logging.</AppText>
          </View>
        ) : filtered.length === 0 ? (
          <View style={styles.inlineNoticeCard}>
            <AppText style={styles.inlineNoticeTitle}>No confirmed items yet</AppText>
            <AppText style={styles.inlineNoticeBody}>
              Confirm closet items first so Tenue can attach them to a wear event.
            </AppText>
          </View>
        ) : (
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
                  {item.imageUri ? (
                    <Image contentFit="cover" source={{ uri: item.imageUri }} style={styles.closetTileImage} />
                  ) : (
                    <View style={styles.closetTilePlaceholder}>
                      <Feather color={featurePalette.muted} name="image" size={20} />
                    </View>
                  )}
                  {isSelected ? (
                    <View style={styles.closetSelectionOverlay}>
                      <View style={styles.closetSelectionBadge}>
                        <Feather color="#FFFFFF" name="check" size={14} />
                      </View>
                    </View>
                  ) : null}
                  <View style={styles.closetTileLabelGradient}>
                    <AppText numberOfLines={2} style={styles.closetTileLabel}>
                      {item.title ?? "Closet item"}
                    </AppText>
                  </View>
                </Pressable>
              );
            })}
          </View>
        )}
      </ScrollView>

      {selected.size > 0 ? (
        <View style={styles.bottomCtaShell}>
          <PrimaryActionButton
            label={`Continue with ${selected.size} ${selected.size === 1 ? "item" : "items"}`}
            onPress={() => {
              onConfirm(items.filter((item) => selected.has(item.id)));
            }}
          />
        </View>
      ) : null}
    </SafeAreaView>
  );
}

function LogOutfitReview({
  error,
  items,
  isSubmitting,
  onBack,
  onConfirm,
  onRemoveItem
}: {
  error: string | null;
  items: ClosetSelectionItem[];
  isSubmitting: boolean;
  onBack: () => void;
  onConfirm: () => void;
  onRemoveItem: (id: string) => void;
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

        {error ? (
          <View style={styles.inlineNoticeCard}>
            <AppText style={styles.inlineNoticeTitle}>Wear log could not save</AppText>
            <AppText style={styles.inlineNoticeBody}>{error}</AppText>
          </View>
        ) : null}

        <View style={styles.reviewList}>
          {items.map((item) => (
            <View key={item.id} style={[styles.reviewCard, featureShadows.sm]}>
              {item.imageUri ? (
                <Image contentFit="cover" source={{ uri: item.imageUri }} style={styles.reviewCardImage} />
              ) : (
                <View style={[styles.reviewCardImage, styles.reviewCardPlaceholder]}>
                  <Feather color={featurePalette.muted} name="image" size={18} />
                </View>
              )}
              <View style={styles.reviewCardCopy}>
                <AppText numberOfLines={1} style={styles.reviewCardTitle}>
                  {item.title ?? "Closet item"}
                </AppText>
                <AppText style={styles.reviewCardSubtitle}>
                  {[item.primaryColor, humanizeEnum(item.subcategory ?? item.category ?? "closet item")]
                    .filter(Boolean)
                    .join(" · ")}
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
                    {item.thumbnailUri || item.imageUri ? (
                      <Image
                        contentFit="cover"
                        source={{ uri: item.thumbnailUri ?? item.imageUri ?? "" }}
                        style={styles.reviewPreviewImage}
                      />
                    ) : (
                      <View style={[styles.reviewPreviewImage, styles.reviewCardPlaceholder]}>
                        <Feather color={featurePalette.muted} name="image" size={18} />
                      </View>
                    )}
                  </View>
                ))}
              </View>
            </ScrollView>
          </View>
        ) : null}
      </ScrollView>

      <View style={styles.bottomCtaShell}>
        <PrimaryActionButton
          disabled={items.length === 0 || isSubmitting}
          label={isSubmitting ? "Saving…" : "Log Outfit"}
          onPress={onConfirm}
        />
      </View>
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
  processingErrorCard: {
    width: "100%",
    maxWidth: 360,
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 20,
    paddingVertical: 20,
    gap: 12
  },
  processingErrorActions: {
    gap: 10,
    marginTop: 4
  },
  processingSecondaryButton: {
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: featurePalette.secondary
  },
  processingSecondaryButtonLabel: {
    ...featureTypography.bodyStrong,
    fontSize: 13
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
  inlineNoticeCard: {
    marginHorizontal: 20,
    marginBottom: 16,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 14
  },
  inlineNoticeTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.darkText,
    marginBottom: 4
  },
  inlineNoticeBody: {
    ...featureTypography.label,
    fontSize: 13,
    lineHeight: 18
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
  closetTilePlaceholder: {
    width: "100%",
    height: "100%",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F8F4FF"
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
  reviewCardPlaceholder: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: featurePalette.secondary
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
