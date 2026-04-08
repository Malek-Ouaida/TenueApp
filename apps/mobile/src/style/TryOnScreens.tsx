import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import {
  type DimensionValue,
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { fontFamilies } from "../theme";
import { AppText } from "../ui";
import { CATEGORY_LABELS, CLOSET_ITEMS, getClosetItemsByIds } from "../lib/reference/wardrobe";
import { launchCameraForSingleImage, launchLibraryForImages } from "../media/picker";
import { featurePalette, featureShadows } from "../theme/feature";
import { Chip, LoadingState, FeatureScreen, SurfaceIconButton } from "../ui/feature-surfaces";

type Mode = "closet" | "trybuy";
type ViewMode = "front" | "side";

const CAPTURE_STEPS = [
  { label: "Front view", instruction: "Stand straight, arms relaxed", sublabel: "Face the camera directly" },
  { label: "Side view", instruction: "Turn to your left side", sublabel: "Keep posture natural" }
] as const;

const CATEGORY_POSITIONS: Record<string, { top: DimensionValue; height: DimensionValue }> = {
  tops: { top: "22%", height: "28%" },
  outerwear: { top: "18%", height: "35%" },
  bottoms: { top: "48%", height: "30%" },
  dresses: { top: "22%", height: "50%" },
  shoes: { top: "80%", height: "14%" },
  bags: { top: "40%", height: "18%" },
  accessories: { top: "10%", height: "12%" }
};

export function TryOnCaptureScreen() {
  const params = useLocalSearchParams<{ itemIds?: string }>();
  const [step, setStep] = useState(0);
  const [photos, setPhotos] = useState<Array<string | null>>([null, null]);

  async function handleCapture() {
    const uri = await launchCameraForSingleImage();
    if (!uri) {
      return;
    }

    setPhotos((current) => {
      const next = [...current];
      next[step] = uri;
      return next;
    });

    if (step === 0) {
      setTimeout(() => setStep(1), 600);
    }
  }

  function handleContinue() {
    router.push(
      ({
        pathname: "/try-on/experience",
        params: {
          frontUri: photos[0] ?? "",
          sideUri: photos[1] ?? "",
          itemIds: typeof params.itemIds === "string" ? params.itemIds : ""
        }
      } as unknown) as Href
    );
  }

  return (
    <View style={styles.captureScreen}>
      {photos[step] ? <Image contentFit="cover" source={{ uri: photos[step] ?? "" }} style={StyleSheet.absoluteFillObject} /> : null}
      <View style={styles.captureOverlay} />

      <View style={styles.captureTopBar}>
        <SurfaceIconButton
          icon={<Feather color="#FFFFFF" name="arrow-left" size={20} />}
          onPress={() => router.back()}
          translucent
        />

        <View style={styles.captureProgress}>
          {CAPTURE_STEPS.map((_, index) => (
            <View
              key={index}
              style={[
                styles.captureProgressSegment,
                index === step ? styles.captureProgressSegmentActive : null,
                index < step && photos[index] ? styles.captureProgressSegmentDone : null
              ]}
            />
          ))}
        </View>

        {photos[step] ? (
          <SurfaceIconButton
            icon={<Feather color="#FFFFFF" name="rotate-ccw" size={16} />}
            onPress={() =>
              setPhotos((current) => {
                const next = [...current];
                next[step] = null;
                return next;
              })
            }
            translucent
          />
        ) : (
          <View style={styles.topSpacer} />
        )}
      </View>

      {!photos[step] ? (
        <View style={styles.silhouetteWrap}>
          <View style={styles.silhouetteHead} />
          <View style={styles.silhouetteBody} />
          <View style={styles.silhouetteLegLeft} />
          <View style={styles.silhouetteLegRight} />
        </View>
      ) : null}

      <View style={styles.captureBottom}>
        <LinearGradient
          colors={["transparent", "rgba(15,23,42,0.62)", "rgba(15,23,42,0.92)"]}
          locations={[0, 0.35, 1]}
          style={StyleSheet.absoluteFillObject}
        />
        <View style={styles.captureTextBlock}>
          <AppText style={styles.captureStep}>Step {step + 1} of 2</AppText>
          <AppText style={styles.captureTitle}>{CAPTURE_STEPS[step]?.label}</AppText>
          <AppText style={styles.captureInstruction}>{CAPTURE_STEPS[step]?.instruction}</AppText>
        </View>

        {!photos[step] ? (
          <Pressable onPress={() => void handleCapture()} style={({ pressed }) => [styles.cameraButtonOuter, pressed ? styles.buttonPressed : null]}>
            <View style={styles.cameraButtonInner}>
              <Feather color={featurePalette.foreground} name="camera" size={24} />
            </View>
          </Pressable>
        ) : step === 1 && photos[0] && photos[1] ? (
          <PrimaryDarkButton label="Build my model" onPress={handleContinue} />
        ) : (
          <View style={styles.captureCheck}>
            <Feather color="#FFFFFF" name="check" size={20} />
          </View>
        )}
      </View>
    </View>
  );
}

export function TryOnExperienceScreen() {
  const params = useLocalSearchParams<{ frontUri?: string; itemIds?: string; sideUri?: string }>();
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<Mode>("closet");
  const [viewMode, setViewMode] = useState<ViewMode>("front");
  const [selectedCategory, setSelectedCategory] = useState("tops");
  const [selectedItemIds, setSelectedItemIds] = useState<number[]>(() => {
    return (params.itemIds ?? "")
      .split(",")
      .map((value) => Number(value))
      .filter((value) => !Number.isNaN(value));
  });
  const [tryBuyImageUri, setTryBuyImageUri] = useState<string | null>(null);

  const frontUri = typeof params.frontUri === "string" ? params.frontUri : null;
  const sideUri = typeof params.sideUri === "string" ? params.sideUri : null;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 3400);
    return () => clearTimeout(timer);
  }, []);

  const selectedItems = useMemo(() => getClosetItemsByIds(selectedItemIds), [selectedItemIds]);
  const categories = Object.keys(CATEGORY_LABELS);
  const bodyPhoto = viewMode === "front" ? frontUri : sideUri;

  if (loading) {
    return (
      <LoadingState
        backgroundUri={frontUri}
        icon={<MaterialCommunityIcons color="#FFFFFF" name="hanger" size={28} />}
        subtitle="Preparing your virtual fit"
        title="Building your model"
        variant="dark"
      />
    );
  }

  async function handleTryBuyUpload() {
    const [uri] = await launchLibraryForImages();
    if (uri) {
      setTryBuyImageUri(uri);
    }
  }

  function toggleClosetItem(id: number) {
    setSelectedItemIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  const displayTitle =
    mode === "closet"
      ? selectedItems.length
        ? `${selectedItems.length} items on`
        : "Build your outfit"
      : "Try before you buy";

  return (
    <View style={styles.experienceScreen}>
      <View style={styles.experienceTopBar}>
        <SurfaceIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
          onPress={() => router.back()}
        />
        <AppText style={styles.experienceTitle}>{displayTitle}</AppText>
        <SurfaceIconButton
          icon={<Feather color={featurePalette.foreground} name="rotate-ccw" size={16} />}
          onPress={() => setViewMode((current) => (current === "front" ? "side" : "front"))}
        />
      </View>

      <View style={styles.modeTabRow}>
        <ModeTab active={mode === "closet"} icon="layers" label="My closet" onPress={() => setMode("closet")} />
        <ModeTab active={mode === "trybuy"} icon="shopping-bag" label="Try before buy" onPress={() => setMode("trybuy")} />
      </View>

      <View style={styles.bodyFrame}>
        {bodyPhoto ? (
          <Image contentFit="contain" source={{ uri: bodyPhoto }} style={styles.bodyImage} />
        ) : (
          <View style={styles.bodyPlaceholder}>
            <Feather color="rgba(100, 116, 139, 0.4)" name="eye" size={40} />
            <AppText style={styles.bodyPlaceholderCopy}>Your model preview</AppText>
          </View>
        )}

        {mode === "closet"
          ? selectedItems.map((item) => {
              const position = CATEGORY_POSITIONS[item.category] ?? { top: "30%", height: "25%" };
              return (
                <View
                  key={item.id}
                  style={[
                    styles.overlayItem,
                    {
                      top: position.top,
                      height: position.height
                    }
                  ]}
                >
                  <Image contentFit="contain" source={item.image} style={styles.overlayItemImage} />
                </View>
              );
            })
          : tryBuyImageUri ? (
            <View style={[styles.overlayItem, { top: "20%", height: "35%" }]}>
              <Image contentFit="contain" source={{ uri: tryBuyImageUri }} style={styles.overlayItemImage} />
            </View>
          ) : null}
      </View>

      <View style={[styles.bottomPanel, featureShadows.md]}>
        {mode === "closet" ? (
          <View style={styles.bottomPanelInner}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.categoryRail}>
              {categories.map((category) => (
                <Chip
                  key={category}
                  active={selectedCategory === category}
                  label={CATEGORY_LABELS[category] ?? category}
                  onPress={() => setSelectedCategory(category)}
                />
              ))}
            </ScrollView>

            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.itemRail}>
              {CLOSET_ITEMS.filter((item) => item.category === selectedCategory).map((item) => {
                const selected = selectedItemIds.includes(item.id);

                return (
                  <Pressable
                    key={item.id}
                    onPress={() => toggleClosetItem(item.id)}
                    style={({ pressed }) => [styles.closetThumbWrap, pressed ? styles.buttonPressed : null]}
                  >
                    <Image contentFit="cover" source={item.image} style={[styles.closetThumb, selected ? styles.closetThumbSelected : null]} />
                    {selected ? (
                      <View style={styles.selectedBadge}>
                        <Feather color="#FFFFFF" name="check" size={12} />
                      </View>
                    ) : null}
                  </Pressable>
                );
              })}
            </ScrollView>

            {selectedItems.length ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.selectedRail}>
                {selectedItems.map((item) => (
                  <Pressable
                    key={item.id}
                    onPress={() => toggleClosetItem(item.id)}
                    style={({ pressed }) => [styles.selectedThumbWrap, pressed ? styles.buttonPressed : null]}
                  >
                    <Image contentFit="cover" source={item.image} style={styles.selectedThumb} />
                    <View style={styles.removeBadge}>
                      <Feather color="#FFFFFF" name="x" size={10} />
                    </View>
                  </Pressable>
                ))}
              </ScrollView>
            ) : null}

            <View style={styles.dualActionRow}>
              <PrimaryLightButton disabled={!selectedItems.length} icon="bookmark" label="Save look" onPress={() => {}} />
              <SecondaryActionButton disabled={!selectedItems.length} icon="edit-3" label="Log outfit" onPress={() => {}} />
            </View>
          </View>
        ) : (
          <View style={styles.bottomPanelInner}>
            {!tryBuyImageUri ? (
              <Pressable onPress={() => void handleTryBuyUpload()} style={({ pressed }) => [styles.tryBuyDropzone, pressed ? styles.buttonPressed : null]}>
                <View style={styles.tryBuyDropzoneIcon}>
                  <Feather color={featurePalette.muted} name="image" size={20} />
                </View>
                <View style={styles.tryBuyDropzoneCopy}>
                  <AppText style={styles.tryBuyDropzoneTitle}>Upload an item</AppText>
                  <AppText style={styles.tryBuyDropzoneSubtitle}>See how it looks on you</AppText>
                </View>
              </Pressable>
            ) : (
              <>
                <View style={styles.tryBuySummary}>
                  <Image contentFit="cover" source={{ uri: tryBuyImageUri }} style={styles.tryBuySummaryImage} />
                  <View style={styles.tryBuySummaryCopy}>
                    <AppText style={styles.tryBuyDropzoneTitle}>Trying this on</AppText>
                    <AppText style={styles.tryBuyDropzoneSubtitle}>See how it fits your style</AppText>
                  </View>
                  <SurfaceIconButton
                    icon={<Feather color={featurePalette.foreground} name="rotate-cw" size={16} />}
                    onPress={() => setTryBuyImageUri(null)}
                  />
                </View>

                <View style={styles.dualActionRow}>
                  <PrimaryLightButton icon="shopping-bag" label="I'll buy it" onPress={() => {}} />
                  <SecondaryActionButton icon="refresh-cw" label="Try another" onPress={() => setTryBuyImageUri(null)} />
                </View>
              </>
            )}
          </View>
        )}
      </View>
    </View>
  );
}

export function TryOnCompareScreen() {
  const [activeIndex, setActiveIndex] = useState(0);
  const looks = [
    { id: 1, label: "Look A", itemIds: [1, 2, 3] },
    { id: 2, label: "Look B", itemIds: [4, 5, 6] }
  ] as const;

  const activeItems = getClosetItemsByIds([...looks[activeIndex].itemIds]);

  return (
    <FeatureScreen contentContainerStyle={styles.compareScreenContent}>
      <View style={styles.compareHeader}>
        <SurfaceIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
          onPress={() => router.back()}
        />
        <AppText style={styles.compareEyebrow}>Compare</AppText>
        <View style={styles.topSpacer} />
      </View>

      <View style={styles.compareTitleBlock}>
        <AppText style={styles.compareMainTitle}>Which suits you better?</AppText>
      </View>

      <View style={styles.compareCards}>
        {looks.map((look, index) => (
          <Pressable
            key={look.id}
            onPress={() => setActiveIndex(index)}
            style={({ pressed }) => [styles.compareLookCard, activeIndex === index ? styles.compareLookCardActive : null, pressed ? styles.buttonPressed : null]}
          >
            <LinearGradient
              colors={["rgba(255,255,255,0.12)", "rgba(15,23,42,0.18)"]}
              style={StyleSheet.absoluteFillObject}
            />
            <View style={styles.compareLookBadge}>
              <AppText style={styles.compareLookBadgeLabel}>{look.label}</AppText>
            </View>
          </Pressable>
        ))}
      </View>

      <View style={styles.compareItemsSection}>
        <AppText style={styles.sectionEyebrow}>{looks[activeIndex].label} items</AppText>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {activeItems.map((item) => (
            <View key={item.id} style={styles.compareItemCard}>
              <View style={styles.compareItemFrame}>
                <Image contentFit="cover" source={item.image} style={styles.compareItemImage} />
              </View>
              <AppText style={styles.compareItemLabel}>{item.title}</AppText>
            </View>
          ))}
        </ScrollView>
      </View>

      <View style={styles.footerPad}>
        <PrimaryLightButton label={`Go with ${looks[activeIndex].label}`} onPress={() => router.back()} />
      </View>
    </FeatureScreen>
  );
}

function ModeTab({
  active,
  icon,
  label,
  onPress
}: {
  active: boolean;
  icon: keyof typeof Feather.glyphMap;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.modeTab, active ? styles.modeTabActive : styles.modeTabIdle, pressed ? styles.buttonPressed : null]}>
      <Feather color={active ? "#FFFFFF" : featurePalette.muted} name={icon} size={14} />
      <AppText style={[styles.modeTabLabel, active ? styles.modeTabLabelActive : null]}>{label}</AppText>
    </Pressable>
  );
}

function PrimaryDarkButton({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.primaryDarkButton, pressed ? styles.buttonPressed : null]}>
      <AppText style={styles.primaryDarkButtonLabel}>{label}</AppText>
    </Pressable>
  );
}

function PrimaryLightButton({
  disabled,
  icon,
  label,
  onPress
}: {
  disabled?: boolean;
  icon?: keyof typeof Feather.glyphMap;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.primaryLightButton,
        disabled ? styles.primaryLightButtonDisabled : null,
        pressed && !disabled ? styles.buttonPressed : null
      ]}
    >
      {icon ? <Feather color={disabled ? featurePalette.muted : "#FFFFFF"} name={icon} size={16} /> : null}
      <AppText style={[styles.primaryLightButtonLabel, disabled ? styles.primaryLightButtonLabelDisabled : null]}>{label}</AppText>
    </Pressable>
  );
}

function SecondaryActionButton({
  disabled,
  icon,
  label,
  onPress
}: {
  disabled?: boolean;
  icon: keyof typeof Feather.glyphMap;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.secondaryActionButton,
        disabled ? styles.secondaryActionButtonDisabled : null,
        pressed && !disabled ? styles.buttonPressed : null
      ]}
    >
      <Feather color={disabled ? featurePalette.muted : featurePalette.foreground} name={icon} size={16} />
      <AppText style={[styles.secondaryActionButtonLabel, disabled ? styles.secondaryActionButtonLabelDisabled : null]}>{label}</AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  buttonPressed: {
    opacity: 0.9,
    transform: [{ scale: 0.98 }]
  },
  topSpacer: {
    width: 40
  },
  captureScreen: {
    flex: 1,
    backgroundColor: featurePalette.foreground
  },
  captureOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(15,23,42,0.5)"
  },
  captureTopBar: {
    position: "absolute",
    top: 56,
    left: 24,
    right: 24,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    zIndex: 2
  },
  captureProgress: {
    flexDirection: "row",
    gap: 8
  },
  captureProgressSegment: {
    width: 16,
    height: 4,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.2)"
  },
  captureProgressSegmentActive: {
    width: 32,
    backgroundColor: "#FFFFFF"
  },
  captureProgressSegmentDone: {
    backgroundColor: "rgba(255,255,255,0.6)"
  },
  silhouetteWrap: {
    position: "absolute",
    top: "20%",
    alignSelf: "center",
    width: 160,
    height: 340,
    alignItems: "center",
    justifyContent: "flex-start",
    opacity: 0.25
  },
  silhouetteHead: {
    width: 44,
    height: 54,
    borderRadius: 24,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: "#FFFFFF"
  },
  silhouetteBody: {
    width: 96,
    height: 170,
    borderRadius: 48,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: "#FFFFFF",
    marginTop: 16
  },
  silhouetteLegLeft: {
    position: "absolute",
    bottom: 28,
    left: 48,
    width: 22,
    height: 110,
    borderRadius: 16,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: "#FFFFFF"
  },
  silhouetteLegRight: {
    position: "absolute",
    bottom: 28,
    right: 48,
    width: 22,
    height: 110,
    borderRadius: 16,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: "#FFFFFF"
  },
  captureBottom: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: 24,
    paddingTop: 84,
    paddingBottom: 32,
    alignItems: "center",
    overflow: "hidden"
  },
  captureTextBlock: {
    alignItems: "center",
    marginBottom: 24
  },
  captureStep: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    color: "rgba(255,255,255,0.6)"
  },
  captureTitle: {
    marginTop: 8,
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 24,
    lineHeight: 28,
    color: "#FFFFFF"
  },
  captureInstruction: {
    marginTop: 6,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 20,
    color: "rgba(255,255,255,0.75)"
  },
  cameraButtonOuter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 3,
    borderColor: "rgba(255,255,255,0.4)",
    alignItems: "center",
    justifyContent: "center"
  },
  cameraButtonInner: {
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  captureCheck: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "rgba(255,255,255,0.2)",
    alignItems: "center",
    justifyContent: "center"
  },
  primaryDarkButton: {
    width: "100%",
    height: 56,
    borderRadius: 28,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  primaryDarkButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 16,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  experienceScreen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  experienceTopBar: {
    paddingTop: 56,
    paddingHorizontal: 24,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  experienceTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  modeTabRow: {
    paddingHorizontal: 24,
    paddingTop: 12,
    flexDirection: "row",
    gap: 8
  },
  modeTab: {
    flex: 1,
    height: 40,
    borderRadius: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6
  },
  modeTabActive: {
    backgroundColor: featurePalette.foreground
  },
  modeTabIdle: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: featurePalette.border
  },
  modeTabLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 16,
    color: featurePalette.muted
  },
  modeTabLabelActive: {
    color: "#FFFFFF"
  },
  bodyFrame: {
    flex: 1,
    marginHorizontal: 24,
    marginTop: 16,
    borderRadius: 24,
    overflow: "hidden",
    backgroundColor: "rgba(226,232,240,0.35)",
    alignItems: "center",
    justifyContent: "center"
  },
  bodyImage: {
    width: "100%",
    height: "100%"
  },
  bodyPlaceholder: {
    alignItems: "center"
  },
  bodyPlaceholderCopy: {
    marginTop: 8,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.muted
  },
  overlayItem: {
    position: "absolute",
    left: "15%",
    right: "15%",
    alignItems: "center",
    justifyContent: "center"
  },
  overlayItemImage: {
    width: "100%",
    height: "100%",
    opacity: 0.88
  },
  bottomPanel: {
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    backgroundColor: "#FFFFFF",
    paddingTop: 18,
    paddingBottom: 30,
    marginTop: 16
  },
  bottomPanelInner: {
    paddingHorizontal: 24
  },
  categoryRail: {
    marginBottom: 12
  },
  itemRail: {
    marginBottom: 16
  },
  closetThumbWrap: {
    marginRight: 10
  },
  closetThumb: {
    width: 68,
    height: 68,
    borderRadius: 18
  },
  closetThumbSelected: {
    borderWidth: 2,
    borderColor: featurePalette.foreground
  },
  selectedBadge: {
    position: "absolute",
    top: -4,
    right: -4,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: featurePalette.foreground,
    alignItems: "center",
    justifyContent: "center"
  },
  selectedRail: {
    marginBottom: 16
  },
  selectedThumbWrap: {
    marginRight: 10
  },
  selectedThumb: {
    width: 40,
    height: 40,
    borderRadius: 12
  },
  removeBadge: {
    position: "absolute",
    top: -4,
    right: -4,
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: featurePalette.muted,
    alignItems: "center",
    justifyContent: "center"
  },
  dualActionRow: {
    flexDirection: "row",
    gap: 10
  },
  primaryLightButton: {
    flex: 1,
    height: 48,
    borderRadius: 24,
    backgroundColor: featurePalette.foreground,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  primaryLightButtonDisabled: {
    backgroundColor: "#D9DEE7"
  },
  primaryLightButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: "#FFFFFF"
  },
  primaryLightButtonLabelDisabled: {
    color: featurePalette.muted
  },
  secondaryActionButton: {
    flex: 1,
    height: 48,
    borderRadius: 24,
    backgroundColor: featurePalette.secondary,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  secondaryActionButtonDisabled: {
    backgroundColor: "#EEF1F5"
  },
  secondaryActionButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  secondaryActionButtonLabelDisabled: {
    color: featurePalette.muted
  },
  tryBuyDropzone: {
    minHeight: 96,
    borderRadius: 20,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: featurePalette.border,
    backgroundColor: featurePalette.background,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    paddingHorizontal: 16
  },
  tryBuyDropzoneIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  tryBuyDropzoneCopy: {
    flex: 1
  },
  tryBuyDropzoneTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  tryBuyDropzoneSubtitle: {
    marginTop: 4,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  tryBuySummary: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 18
  },
  tryBuySummaryImage: {
    width: 64,
    height: 64,
    borderRadius: 16
  },
  tryBuySummaryCopy: {
    flex: 1
  },
  compareScreenContent: {
    paddingTop: 56,
    paddingHorizontal: 24,
    paddingBottom: 40
  },
  compareHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 20
  },
  compareEyebrow: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  compareTitleBlock: {
    marginBottom: 20
  },
  compareMainTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 26,
    lineHeight: 32,
    letterSpacing: -0.48,
    color: featurePalette.foreground
  },
  compareCards: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 24
  },
  compareLookCard: {
    flex: 1,
    aspectRatio: 3 / 5,
    borderRadius: 24,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  compareLookCardActive: {
    borderWidth: 2,
    borderColor: featurePalette.foreground
  },
  compareLookBadge: {
    position: "absolute",
    left: 12,
    bottom: 12,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.82)"
  },
  compareLookBadgeLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  compareItemsSection: {
    marginBottom: 24
  },
  compareItemCard: {
    width: 80,
    marginRight: 12
  },
  compareItemFrame: {
    aspectRatio: 1,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 6
  },
  compareItemImage: {
    width: "100%",
    height: "100%"
  },
  compareItemLabel: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.foreground
  },
  footerPad: {
    marginTop: 8
  },
  sectionEyebrow: {
    marginBottom: 12,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    color: featurePalette.muted
  }
});
