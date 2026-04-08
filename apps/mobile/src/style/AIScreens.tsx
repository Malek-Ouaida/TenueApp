import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
  type NativeScrollEvent,
  type NativeSyntheticEvent
} from "react-native";

import { fontFamilies } from "../theme";
import { AppText } from "../ui";
import { CLOSET_ITEMS, getClosetItemsByIds } from "../lib/reference/wardrobe";
import { launchLibraryForImages } from "../media/picker";
import { featurePalette, featureShadows } from "../theme/feature";
import { Chip, LoadingState, FeatureScreen, StickyActionBar, SurfaceIconButton } from "../ui/feature-surfaces";

const OCCASIONS = ["Wedding", "Dinner", "Date Night", "Presentation", "Party", "Brunch", "Work", "Travel"] as const;
const DRESS_CODES = ["Formal", "Smart Casual", "Business Casual", "Casual", "Black Tie", "Cocktail"] as const;
const VIBES = ["Polished", "Elegant", "Relaxed", "Bold", "Minimal", "Edgy", "Romantic"] as const;
const PREFS = ["No heels", "Use black blazer", "Avoid denim", "No accessories", "Prefer layers", "Keep it simple"] as const;

const FIT_CHECK_RESULT = {
  score: 8.4,
  verdict: "Well-balanced and event-appropriate. A few small tweaks could elevate this further.",
  subScores: [
    { label: "Occasion fit", score: 9 },
    { label: "Dress code match", score: 8 },
    { label: "Color harmony", score: 8.5 },
    { label: "Styling polish", score: 7.5 }
  ],
  works: [
    "Silhouette is clean and proportional",
    "Color palette feels cohesive and intentional",
    "The tailored blazer elevates the whole look"
  ],
  improve: [
    "Shoes feel slightly too casual for this dress code",
    "Consider a more structured bag to match the formality"
  ],
  suggestions: [
    { action: "Replace", item: "White sneakers", with: "Leather loafers or minimal ankle boots" },
    { action: "Add", item: "A simple watch or bracelet", with: "To polish the overall styling" }
  ]
} as const;

const STYLE_LOOKS = [
  {
    id: "1",
    title: "Polished & effortless",
    why: "Balanced, elevated, and event-appropriate. The silhouette is clean and the palette feels refined.",
    itemIds: [7, 3, 2, 6]
  },
  {
    id: "2",
    title: "Quietly bold",
    why: "A subtle statement that feels intentional. Rich textures paired with a confident shape.",
    itemIds: [4, 5, 9, 6]
  },
  {
    id: "3",
    title: "Relaxed elegance",
    why: "Soft layers with structure. The contrast between casual and polished creates interest.",
    itemIds: [1, 8, 10, 6]
  }
] as const;

const SCORE_LABELS = {
  high: "Strong choice",
  good: "Great fit",
  mid: "Almost there",
  low: "Needs refinement"
} as const;

export function AIStylistScreen() {
  return (
    <FeatureScreen contentContainerStyle={styles.screenContent}>
      <SurfaceIconButton
        icon={<Feather color={featurePalette.foreground} name="arrow-left" size={20} />}
        onPress={() => router.back()}
      />

      <View style={styles.heroTitleBlock}>
        <AppText style={styles.pageTitle}>AI Stylist</AppText>
        <AppText style={styles.pageSubtitle}>Your personal styling intelligence</AppText>
      </View>

      <FeatureCard
        backgroundColors={["rgba(232, 219, 255, 0.6)", "rgba(255,255,255,0)"]}
        copy="Upload a photo and get feedback for your event"
        eyebrow="Rating · Feedback · Suggestions"
        icon={<Feather color={featurePalette.foreground} name="camera" size={24} />}
        onPress={() => router.push("/ai-stylist/fit-check")}
        title="Check my outfit"
      />

      <FeatureCard
        backgroundColors={["rgba(216, 235, 207, 0.5)", "rgba(255, 244, 214, 0.3)"]}
        copy="Get 3 complete outfit suggestions from your closet"
        eyebrow="3 Looks · Full outfits · Save & log"
        icon={<MaterialCommunityIcons color={featurePalette.foreground} name="hanger" size={24} />}
        onPress={() => router.push("/ai-stylist/style-me")}
        title="Style me"
      />
    </FeatureScreen>
  );
}

export function FitCheckScreen() {
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [occasion, setOccasion] = useState<string | null>(null);
  const [dressCode, setDressCode] = useState<string | null>(null);
  const [vibe, setVibe] = useState<string | null>(null);

  async function handleImageUpload() {
    const [uri] = await launchLibraryForImages();
    if (uri) {
      setImageUri(uri);
    }
  }

  const canSubmit = Boolean(imageUri && occasion && dressCode);

  function handleSubmit() {
    if (!canSubmit || !imageUri || !occasion || !dressCode) {
      return;
    }

    router.push(
      ({
        pathname: "/ai-stylist/fit-check/results",
        params: {
          imageUri,
          occasion,
          dressCode,
          vibe: vibe ?? ""
        }
      } as unknown) as Href
    );
  }

  return (
    <View style={styles.fullScreen}>
      <FeatureScreen contentContainerStyle={styles.flowScreenContent} style={styles.flowScreen}>
        <SurfaceIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={20} />}
          onPress={() => router.back()}
        />

        <View style={styles.flowTitleBlock}>
          <AppText style={styles.flowTitle}>Check my outfit</AppText>
          <AppText style={styles.flowSubtitle}>Upload your look and tell us the occasion</AppText>
        </View>

        {imageUri ? (
          <View style={styles.uploadPreview}>
            <Image contentFit="cover" source={{ uri: imageUri }} style={styles.uploadPreviewImage} />
            <Pressable onPress={() => setImageUri(null)} style={styles.uploadPreviewClear}>
              <Feather color="#FFFFFF" name="x" size={16} />
            </Pressable>
          </View>
        ) : (
          <UploadDropzone
            copy="Add your photo"
            subtitle="Tap to upload or take a photo"
            onPress={() => void handleImageUpload()}
          />
        )}

        <ChoiceSection title="Occasion">
          {OCCASIONS.map((item) => (
            <Chip key={item} active={occasion === item} label={item} onPress={() => setOccasion(occasion === item ? null : item)} />
          ))}
        </ChoiceSection>

        <ChoiceSection title="Dress Code">
          {DRESS_CODES.map((item) => (
            <Chip key={item} active={dressCode === item} label={item} onPress={() => setDressCode(dressCode === item ? null : item)} />
          ))}
        </ChoiceSection>

        <ChoiceSection title="Vibe (optional)">
          {VIBES.map((item) => (
            <Chip key={item} active={vibe === item} label={item} onPress={() => setVibe(vibe === item ? null : item)} />
          ))}
        </ChoiceSection>
      </FeatureScreen>

      <StickyActionBar>
        <PrimaryPillButton
          disabled={!canSubmit}
          label="Analyze my outfit"
          onPress={handleSubmit}
        />
      </StickyActionBar>
    </View>
  );
}

export function FitCheckResultsScreen() {
  const params = useLocalSearchParams<{
    dressCode?: string;
    imageUri?: string;
    occasion?: string;
  }>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 2800);
    return () => clearTimeout(timer);
  }, []);

  const imageUri = typeof params.imageUri === "string" ? params.imageUri : null;
  const occasion = typeof params.occasion === "string" ? params.occasion : "";
  const dressCode = typeof params.dressCode === "string" ? params.dressCode : "";

  if (loading) {
    return (
      <LoadingState
        backgroundUri={imageUri}
        icon={<MaterialCommunityIcons color={featurePalette.foreground} name="star-four-points" size={30} />}
        subtitle="Reviewing fit, balance, and occasion match"
        title="Analyzing your look"
      />
    );
  }

  return (
    <ScrollView bounces={false} contentContainerStyle={styles.resultsContent} showsVerticalScrollIndicator={false} style={styles.fullScreen}>
      <View style={styles.resultsHero}>
        {imageUri ? <Image contentFit="cover" source={{ uri: imageUri }} style={styles.resultsHeroImage} /> : null}
        <LinearGradient
          colors={["transparent", "rgba(250,249,247,0.15)", featurePalette.background]}
          locations={[0, 0.6, 1]}
          style={StyleSheet.absoluteFillObject}
        />
        <View style={styles.resultsHeroTop}>
          <SurfaceIconButton
            icon={<Feather color={featurePalette.foreground} name="arrow-left" size={20} />}
            onPress={() => router.back()}
            translucent
          />
        </View>
        <View style={styles.resultsScoreWrap}>
          <View>
            <AppText style={styles.resultsMeta}>{occasion} · {dressCode}</AppText>
            <AppText style={styles.resultsLabel}>{getScoreLabel(FIT_CHECK_RESULT.score)}</AppText>
          </View>
          <View style={styles.resultsScoreRow}>
            <AppText style={styles.resultsScoreValue}>{FIT_CHECK_RESULT.score}</AppText>
            <AppText style={styles.resultsScoreOutOf}>/10</AppText>
          </View>
        </View>
      </View>

      <View style={styles.subScoreGrid}>
        {FIT_CHECK_RESULT.subScores.map((item) => (
          <View key={item.label} style={[styles.subScoreCard, featureShadows.sm]}>
            <AppText style={styles.subScoreLabel}>{item.label}</AppText>
            <View style={styles.subScoreValueRow}>
              <AppText style={styles.subScoreValue}>{item.score}</AppText>
              <AppText style={styles.subScoreValueSuffix}>/10</AppText>
            </View>
            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: `${item.score * 10}%` }]} />
            </View>
          </View>
        ))}
      </View>

      <AppText style={styles.verdictCopy}>{FIT_CHECK_RESULT.verdict}</AppText>

      <InsightCard
        icon={<Feather color={featurePalette.foreground} name="check" size={16} />}
        iconBackground="rgba(110, 197, 170, 0.28)"
        items={FIT_CHECK_RESULT.works}
        title="What works"
      />

      <InsightCard
        icon={<Feather color={featurePalette.foreground} name="alert-triangle" size={16} />}
        iconBackground="rgba(255, 212, 122, 0.45)"
        items={FIT_CHECK_RESULT.improve}
        title="What to improve"
      />

      <View style={[styles.insightCard, featureShadows.sm]}>
        <View style={styles.insightCardHeader}>
          <View style={[styles.insightIcon, { backgroundColor: "rgba(232, 219, 255, 0.55)" }]}>
            <Feather color={featurePalette.foreground} name="arrow-up-right" size={16} />
          </View>
          <AppText style={styles.insightCardTitle}>Suggested changes</AppText>
        </View>
        <View style={styles.suggestionStack}>
          {FIT_CHECK_RESULT.suggestions.map((item) => (
            <View key={item.item} style={styles.suggestionItem}>
              <View style={styles.suggestionBadge}>
                <AppText style={styles.suggestionBadgeLabel}>{item.action}</AppText>
              </View>
              <AppText style={styles.suggestionItemTitle}>{item.item}</AppText>
              <AppText style={styles.suggestionItemCopy}>{item.with}</AppText>
            </View>
          ))}
        </View>
      </View>

      <View style={styles.actionStack}>
        <PrimaryPillButton label="Show better options" onPress={() => {}} />
        <View style={styles.splitActions}>
          <SecondaryPillButton icon="bookmark" label="Save" onPress={() => {}} />
          <SecondaryPillButton icon="edit-3" label="Log outfit" onPress={() => {}} />
        </View>
      </View>
    </ScrollView>
  );
}

export function StyleMeScreen() {
  const [occasion, setOccasion] = useState<string | null>(null);
  const [dressCode, setDressCode] = useState<string | null>(null);
  const [vibe, setVibe] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<string[]>([]);

  const canSubmit = Boolean(occasion && dressCode);

  function handleSubmit() {
    if (!occasion || !dressCode) {
      return;
    }

    router.push(
      ({
        pathname: "/ai-stylist/style-me/results",
        params: {
          occasion,
          dressCode,
          vibe: vibe ?? "",
          prefs: prefs.join("|")
        }
      } as unknown) as Href
    );
  }

  function togglePref(pref: string) {
    setPrefs((current) => (current.includes(pref) ? current.filter((item) => item !== pref) : [...current, pref]));
  }

  return (
    <View style={styles.fullScreen}>
      <FeatureScreen contentContainerStyle={styles.flowScreenContent} style={styles.flowScreen}>
        <SurfaceIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={20} />}
          onPress={() => router.back()}
        />

        <View style={styles.flowTitleBlock}>
          <AppText style={styles.flowTitle}>Style me</AppText>
          <AppText style={styles.flowSubtitle}>Tell us the occasion and we'll build your looks</AppText>
        </View>

        <ChoiceSection title="Occasion">
          {OCCASIONS.map((item) => (
            <Chip key={item} active={occasion === item} label={item} onPress={() => setOccasion(occasion === item ? null : item)} />
          ))}
        </ChoiceSection>

        <ChoiceSection title="Dress Code">
          {DRESS_CODES.map((item) => (
            <Chip key={item} active={dressCode === item} label={item} onPress={() => setDressCode(dressCode === item ? null : item)} />
          ))}
        </ChoiceSection>

        <ChoiceSection title="Vibe (optional)">
          {VIBES.map((item) => (
            <Chip key={item} active={vibe === item} label={item} onPress={() => setVibe(vibe === item ? null : item)} />
          ))}
        </ChoiceSection>

        <ChoiceSection title="Preferences (optional)">
          {PREFS.map((item) => (
            <Chip key={item} active={prefs.includes(item)} label={item} onPress={() => togglePref(item)} />
          ))}
        </ChoiceSection>
      </FeatureScreen>

      <StickyActionBar>
        <PrimaryPillButton disabled={!canSubmit} label="Build my looks" onPress={handleSubmit} />
      </StickyActionBar>
    </View>
  );
}

export function StyleMeResultsScreen() {
  const params = useLocalSearchParams<{ dressCode?: string; occasion?: string }>();
  const [loading, setLoading] = useState(true);
  const [currentLook, setCurrentLook] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const { width } = useWindowDimensions();
  const cardWidth = width - 48;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 3200);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <LoadingState
        icon={<MaterialCommunityIcons color={featurePalette.foreground} name="star-four-points" size={30} />}
        subtitle="Matching pieces by vibe and formality"
        title="Building your looks"
      />
    );
  }

  function scrollToLook(index: number) {
    setCurrentLook(index);
    scrollRef.current?.scrollTo({ x: index * cardWidth, animated: true });
  }

  function handleScrollEnd(event: NativeSyntheticEvent<NativeScrollEvent>) {
    const nextIndex = Math.round(event.nativeEvent.contentOffset.x / cardWidth);
    if (nextIndex !== currentLook) {
      setCurrentLook(nextIndex);
    }
  }

  return (
    <ScrollView bounces={false} contentContainerStyle={styles.styleResultsContent} showsVerticalScrollIndicator={false} style={styles.fullScreen}>
      <View style={styles.styleResultsHeader}>
        <SurfaceIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={20} />}
          onPress={() => router.back()}
        />
        <View style={styles.styleResultsTitleBlock}>
          <View>
            <AppText style={styles.detailHeaderTitle}>Your looks</AppText>
            <AppText style={styles.resultsMeta}>
              {params.occasion ?? ""} · {params.dressCode ?? ""}
            </AppText>
          </View>
          <Pressable style={styles.refreshButton}>
            <Feather color={featurePalette.foreground} name="rotate-cw" size={16} />
          </Pressable>
        </View>
      </View>

      <View style={styles.lookTabRow}>
        {STYLE_LOOKS.map((_, index) => (
          <Chip
            key={index}
            active={currentLook === index}
            label={`Look ${index + 1}`}
            onPress={() => scrollToLook(index)}
          />
        ))}
      </View>

      <ScrollView
        ref={scrollRef}
        horizontal
        onMomentumScrollEnd={handleScrollEnd}
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        snapToInterval={cardWidth}
        decelerationRate="fast"
        style={styles.lookCarousel}
      >
        {STYLE_LOOKS.map((look, index) => {
          const items = getClosetItemsByIds([...look.itemIds]);

          return (
            <View key={look.id} style={[styles.lookSlide, { width: cardWidth }]}>
              <View style={[styles.lookCard, featureShadows.md]}>
                <View style={styles.lookGrid}>
                  {items.slice(0, 4).map((item, itemIndex) => (
                    <View
                      key={item.id}
                      style={[
                        styles.lookGridCell,
                        itemIndex === 0 ? styles.lookGridTopLeft : null,
                        itemIndex === 1 ? styles.lookGridTopRight : null,
                        itemIndex === 2 ? styles.lookGridBottomLeft : null,
                        itemIndex === 3 ? styles.lookGridBottomRight : null
                      ]}
                    >
                      <Image contentFit="cover" source={item.image} style={styles.lookGridImage} />
                    </View>
                  ))}
                </View>

                <View style={styles.lookCardBody}>
                  <AppText style={styles.lookEyebrow}>Look {index + 1}</AppText>
                  <AppText style={styles.lookTitle}>{look.title}</AppText>
                  <AppText style={styles.lookWhy}>{look.why}</AppText>

                  <View style={styles.lookItemStack}>
                    {items.map((item) => (
                      <View key={item.id} style={styles.lookItemRow}>
                        <Image contentFit="cover" source={item.image} style={styles.lookItemThumb} />
                        <View style={styles.lookItemCopy}>
                          <AppText style={styles.lookItemTitle}>{item.title}</AppText>
                          <AppText style={styles.lookItemBrand}>{item.brand}</AppText>
                        </View>
                        <Pressable>
                          <Feather color={featurePalette.muted} name="rotate-cw" size={16} />
                        </Pressable>
                      </View>
                    ))}
                  </View>

                  <View style={styles.lookActionStack}>
                    <View style={styles.lookPrimaryActions}>
                      <PrimaryPillButton label="Wear this" onPress={() => {}} />
                      <Pressable
                        onPress={() =>
                          router.push(
                            ({
                              pathname: "/try-on",
                              params: { itemIds: look.itemIds.join(",") }
                            } as unknown) as Href
                          )
                        }
                        style={({ pressed }) => [styles.tryOnButton, pressed ? styles.buttonPressed : null]}
                      >
                        <Feather color={featurePalette.foreground} name="eye" size={16} />
                        <AppText style={styles.tryOnButtonLabel}>Try on</AppText>
                      </Pressable>
                    </View>
                    <View style={styles.lookSecondaryActions}>
                      <SecondaryPillButton icon="bookmark" label="Save" onPress={() => {}} />
                      <SecondaryPillButton icon="edit-3" label="Log outfit" onPress={() => {}} />
                    </View>
                  </View>
                </View>
              </View>

              <View style={styles.refineChipRow}>
                <Chip active={false} label="More formal" onPress={() => {}} />
                <Chip active={false} label="More casual" onPress={() => {}} />
                <Chip active={false} label="Another option" onPress={() => {}} />
              </View>
            </View>
          );
        })}
      </ScrollView>
    </ScrollView>
  );
}

export function OutfitRecommendationDetailScreen() {
  const params = useLocalSearchParams<{ itemIds?: string }>();
  const [saved, setSaved] = useState(false);
  const items = useMemo(() => {
    const ids = (params.itemIds ?? "1,2,3")
      .split(",")
      .map((value) => Number(value))
      .filter((value) => !Number.isNaN(value));

    const matches = getClosetItemsByIds(ids);
    return matches.length ? matches : CLOSET_ITEMS.slice(0, 3);
  }, [params.itemIds]);

  const substitutions = [
    { original: "Brown Boots", alternative: "White sneakers for a relaxed take" },
    { original: "Cream Cardigan", alternative: "Navy blazer for a sharper mood" }
  ];

  return (
    <FeatureScreen contentContainerStyle={styles.recommendationContent}>
      <View style={styles.detailHeader}>
        <SurfaceIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
          onPress={() => router.back()}
        />
        <SurfaceIconButton
          icon={<Feather color={saved ? "#F87171" : featurePalette.foreground} name="heart" size={18} />}
          onPress={() => setSaved((current) => !current)}
        />
      </View>

      <View style={styles.recommendationTitleBlock}>
        <View style={styles.recommendationEyebrowRow}>
          <MaterialCommunityIcons color={featurePalette.muted} name="star-four-points" size={14} />
          <AppText style={styles.lookEyebrow}>Styled for you</AppText>
        </View>
        <AppText style={styles.recommendationTitle}>Effortless Monday</AppText>
        <AppText style={styles.recommendationQuote}>“Refined casual with a confident edge”</AppText>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.recommendationItemsRail}>
        {items.map((item) => (
          <View key={item.id} style={styles.recommendationItemCard}>
            <View style={styles.recommendationItemFrame}>
              <Image contentFit="cover" source={item.image} style={styles.recommendationItemImage} />
            </View>
            <AppText style={styles.lookItemTitle}>{item.title}</AppText>
            <AppText style={styles.lookItemBrand}>{item.brand}</AppText>
          </View>
        ))}
      </ScrollView>

      <View style={[styles.scoreCard, featureShadows.sm]}>
        <View style={styles.scoreCardRow}>
          <AppText style={styles.lookEyebrow}>Style score</AppText>
          <AppText style={styles.scoreCardValue}>9.2</AppText>
        </View>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: "92%" }]} />
        </View>
      </View>

      <View style={styles.recommendationSection}>
        <AppText style={styles.preferenceTitle}>Why it works</AppText>
        <AppText style={styles.verdictCopy}>
          This combination balances structure with softness. The cream cardigan adds warmth while the black trousers ground the look. The brown boots bring it together with a confident, polished finish.
        </AppText>
      </View>

      <View style={styles.recommendationSection}>
        <AppText style={styles.preferenceTitle}>Alternatives</AppText>
        <View style={styles.altStack}>
          {substitutions.map((item) => (
            <View key={item.original} style={[styles.altCard, featureShadows.sm]}>
              <Feather color={featurePalette.muted} name="rotate-cw" size={16} />
              <View style={styles.altCopy}>
                <AppText style={styles.lookItemTitle}>{item.original}</AppText>
                <AppText style={styles.lookItemBrand}>{item.alternative}</AppText>
              </View>
            </View>
          ))}
        </View>
      </View>

      <View style={styles.splitActions}>
        <Pressable
          onPress={() =>
            router.push(
              ({
                pathname: "/try-on/experience",
                params: { itemIds: items.map((item) => item.id).join(",") }
              } as unknown) as Href
            )
          }
          style={({ pressed }) => [styles.secondaryWideButton, pressed ? styles.buttonPressed : null]}
        >
          <Feather color={featurePalette.foreground} name="eye" size={16} />
          <AppText style={styles.secondaryWideButtonLabel}>Try on</AppText>
        </Pressable>
        <PrimaryPillButton label="Save look" onPress={() => setSaved(true)} />
      </View>
    </FeatureScreen>
  );
}

function FeatureCard({
  backgroundColors,
  copy,
  eyebrow,
  icon,
  onPress,
  title
}: {
  backgroundColors: [string, string];
  copy: string;
  eyebrow: string;
  icon: React.ReactNode;
  onPress: () => void;
  title: string;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.featureCard, featureShadows.lg, pressed ? styles.buttonPressed : null]}>
      <LinearGradient colors={backgroundColors} end={{ x: 1, y: 1 }} start={{ x: 0, y: 0 }} style={StyleSheet.absoluteFillObject} />
      <View style={styles.featureIcon}>{icon}</View>
      <AppText style={styles.featureTitle}>{title}</AppText>
      <AppText style={styles.featureCopy}>{copy}</AppText>
      <View style={styles.featureEyebrowRow}>
        <MaterialCommunityIcons color={featurePalette.muted} name="star-four-points" size={14} />
        <AppText style={styles.featureEyebrow}>{eyebrow}</AppText>
      </View>
    </Pressable>
  );
}

function UploadDropzone({
  copy,
  subtitle,
  onPress
}: {
  copy: string;
  subtitle: string;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.dropzone, pressed ? styles.buttonPressed : null]}>
      <View style={styles.dropzoneIcon}>
        <Feather color={featurePalette.muted} name="image" size={26} />
      </View>
      <View style={styles.dropzoneText}>
        <AppText style={styles.dropzoneTitle}>{copy}</AppText>
        <AppText style={styles.dropzoneSubtitle}>{subtitle}</AppText>
      </View>
    </Pressable>
  );
}

function ChoiceSection({
  children,
  title
}: {
  children: React.ReactNode;
  title: string;
}) {
  return (
    <View style={styles.choiceSection}>
      <AppText style={styles.choiceSectionTitle}>{title}</AppText>
      <View style={styles.choiceWrap}>{children}</View>
    </View>
  );
}

function InsightCard({
  icon,
  iconBackground,
  items,
  title
}: {
  icon: React.ReactNode;
  iconBackground: string;
  items: readonly string[];
  title: string;
}) {
  return (
    <View style={[styles.insightCard, featureShadows.sm]}>
      <View style={styles.insightCardHeader}>
        <View style={[styles.insightIcon, { backgroundColor: iconBackground }]}>{icon}</View>
        <AppText style={styles.insightCardTitle}>{title}</AppText>
      </View>
      <View style={styles.insightList}>
        {items.map((item) => (
          <AppText key={item} style={styles.insightItem}>
            {item}
          </AppText>
        ))}
      </View>
    </View>
  );
}

function PrimaryPillButton({
  disabled,
  label,
  onPress
}: {
  disabled?: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.primaryButton,
        disabled ? styles.primaryButtonDisabled : null,
        pressed && !disabled ? styles.buttonPressed : null
      ]}
    >
      <AppText style={[styles.primaryButtonLabel, disabled ? styles.primaryButtonLabelDisabled : null]}>{label}</AppText>
    </Pressable>
  );
}

function SecondaryPillButton({
  icon,
  label,
  onPress
}: {
  icon: keyof typeof Feather.glyphMap;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.secondaryWideButton, pressed ? styles.buttonPressed : null]}>
      <Feather color={featurePalette.foreground} name={icon} size={16} />
      <AppText style={styles.secondaryWideButtonLabel}>{label}</AppText>
    </Pressable>
  );
}

function getScoreLabel(score: number) {
  if (score >= 8.5) {
    return SCORE_LABELS.high;
  }

  if (score >= 7) {
    return SCORE_LABELS.good;
  }

  if (score >= 5) {
    return SCORE_LABELS.mid;
  }

  return SCORE_LABELS.low;
}

const styles = StyleSheet.create({
  fullScreen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  screenContent: {
    paddingTop: 56,
    paddingHorizontal: 24,
    paddingBottom: 36,
    gap: 16
  },
  flowScreen: {
    flex: 1
  },
  flowScreenContent: {
    paddingTop: 56,
    paddingHorizontal: 24,
    paddingBottom: 140
  },
  heroTitleBlock: {
    marginTop: 8,
    marginBottom: 4
  },
  pageTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 32,
    lineHeight: 38,
    letterSpacing: -0.64,
    color: featurePalette.foreground
  },
  pageSubtitle: {
    marginTop: 6,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 22,
    color: featurePalette.muted
  },
  featureCard: {
    borderRadius: 28,
    overflow: "hidden",
    padding: 28,
    backgroundColor: "#FFFFFF"
  },
  featureIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: featurePalette.background,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20
  },
  featureTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 24,
    lineHeight: 28,
    letterSpacing: -0.4,
    color: featurePalette.foreground
  },
  featureCopy: {
    marginTop: 8,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 22,
    color: featurePalette.muted
  },
  featureEyebrowRow: {
    marginTop: 20,
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  featureEyebrow: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted,
    textTransform: "uppercase"
  },
  flowTitleBlock: {
    marginTop: 24,
    marginBottom: 16
  },
  flowTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 28,
    lineHeight: 34,
    letterSpacing: -0.48,
    color: featurePalette.foreground
  },
  flowSubtitle: {
    marginTop: 6,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 20,
    color: featurePalette.muted
  },
  dropzone: {
    marginTop: 8,
    marginBottom: 28,
    aspectRatio: 3 / 4,
    borderRadius: 24,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: featurePalette.border,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    gap: 14
  },
  dropzoneIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: featurePalette.background,
    alignItems: "center",
    justifyContent: "center"
  },
  dropzoneText: {
    alignItems: "center"
  },
  dropzoneTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  dropzoneSubtitle: {
    marginTop: 4,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.muted
  },
  uploadPreview: {
    marginTop: 8,
    marginBottom: 28,
    aspectRatio: 3 / 4,
    borderRadius: 24,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  uploadPreviewImage: {
    width: "100%",
    height: "100%"
  },
  uploadPreviewClear: {
    position: "absolute",
    top: 12,
    right: 12,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(15, 23, 42, 0.7)",
    alignItems: "center",
    justifyContent: "center"
  },
  choiceSection: {
    marginBottom: 24
  },
  choiceSectionTitle: {
    marginBottom: 12,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    color: featurePalette.foreground
  },
  choiceWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  primaryButton: {
    minWidth: 0,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: featurePalette.foreground
  },
  primaryButtonDisabled: {
    backgroundColor: "#D9DEE7"
  },
  primaryButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 16,
    lineHeight: 20,
    color: "#FFFFFF"
  },
  primaryButtonLabelDisabled: {
    color: featurePalette.muted
  },
  buttonPressed: {
    opacity: 0.9,
    transform: [{ scale: 0.98 }]
  },
  resultsContent: {
    paddingBottom: 32
  },
  resultsHero: {
    position: "relative",
    width: "100%",
    aspectRatio: 3 / 4,
    backgroundColor: featurePalette.secondary
  },
  resultsHeroImage: {
    width: "100%",
    height: "100%"
  },
  resultsHeroTop: {
    position: "absolute",
    top: 56,
    left: 24
  },
  resultsScoreWrap: {
    position: "absolute",
    left: 24,
    right: 24,
    bottom: 24,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between"
  },
  resultsMeta: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  resultsLabel: {
    marginTop: 4,
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 18,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  resultsScoreRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 4
  },
  resultsScoreValue: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 48,
    lineHeight: 50,
    color: featurePalette.foreground
  },
  resultsScoreOutOf: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 18,
    lineHeight: 24,
    color: featurePalette.muted
  },
  subScoreGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    paddingHorizontal: 24,
    paddingTop: 24
  },
  subScoreCard: {
    width: "47%",
    borderRadius: 20,
    padding: 16,
    backgroundColor: "#FFFFFF"
  },
  subScoreLabel: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  subScoreValueRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 2,
    marginTop: 8
  },
  subScoreValue: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 22,
    lineHeight: 26,
    color: featurePalette.foreground
  },
  subScoreValueSuffix: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.muted
  },
  progressTrack: {
    marginTop: 10,
    height: 6,
    borderRadius: 999,
    backgroundColor: featurePalette.secondary,
    overflow: "hidden"
  },
  progressFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: featurePalette.sage
  },
  verdictCopy: {
    paddingHorizontal: 24,
    paddingTop: 24,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 24,
    color: featurePalette.foreground
  },
  insightCard: {
    marginTop: 20,
    marginHorizontal: 24,
    borderRadius: 24,
    padding: 24,
    backgroundColor: "#FFFFFF"
  },
  insightCardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 16
  },
  insightIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center"
  },
  insightCardTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  insightList: {
    gap: 10
  },
  insightItem: {
    paddingLeft: 42,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 22,
    color: featurePalette.muted
  },
  suggestionStack: {
    gap: 16
  },
  suggestionItem: {
    paddingLeft: 42
  },
  suggestionBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: featurePalette.secondary,
    marginBottom: 8
  },
  suggestionBadgeLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  suggestionItemTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  suggestionItemCopy: {
    marginTop: 4,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.muted
  },
  actionStack: {
    marginTop: 24,
    paddingHorizontal: 24,
    gap: 12
  },
  splitActions: {
    flexDirection: "row",
    gap: 12
  },
  secondaryWideButton: {
    flex: 1,
    height: 48,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: featurePalette.border,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  secondaryWideButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  styleResultsContent: {
    paddingTop: 56,
    paddingBottom: 32
  },
  styleResultsHeader: {
    paddingHorizontal: 24
  },
  styleResultsTitleBlock: {
    marginTop: 16,
    marginBottom: 12,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between"
  },
  detailHeaderTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 26,
    lineHeight: 32,
    letterSpacing: -0.48,
    color: featurePalette.foreground
  },
  refreshButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: featurePalette.border
  },
  lookTabRow: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 24,
    marginBottom: 20
  },
  lookCarousel: {
    paddingLeft: 24
  },
  lookSlide: {
    paddingRight: 24
  },
  lookCard: {
    borderRadius: 28,
    overflow: "hidden",
    backgroundColor: "#FFFFFF"
  },
  lookGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    padding: 4,
    gap: 2
  },
  lookGridCell: {
    width: "49.5%",
    aspectRatio: 1,
    overflow: "hidden"
  },
  lookGridTopLeft: {
    borderTopLeftRadius: 26
  },
  lookGridTopRight: {
    borderTopRightRadius: 26
  },
  lookGridBottomLeft: {
    borderBottomLeftRadius: 26
  },
  lookGridBottomRight: {
    borderBottomRightRadius: 26
  },
  lookGridImage: {
    width: "100%",
    height: "100%"
  },
  lookCardBody: {
    padding: 24
  },
  lookEyebrow: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  lookTitle: {
    marginTop: 8,
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 22,
    lineHeight: 26,
    letterSpacing: -0.34,
    color: featurePalette.foreground
  },
  lookWhy: {
    marginTop: 10,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 22,
    color: featurePalette.muted
  },
  lookItemStack: {
    marginTop: 18,
    gap: 12
  },
  lookItemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  lookItemThumb: {
    width: 44,
    height: 44,
    borderRadius: 16
  },
  lookItemCopy: {
    flex: 1
  },
  lookItemTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  lookItemBrand: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  lookActionStack: {
    marginTop: 20,
    gap: 10
  },
  lookPrimaryActions: {
    flexDirection: "row",
    gap: 10
  },
  tryOnButton: {
    height: 48,
    paddingHorizontal: 18,
    borderRadius: 24,
    backgroundColor: featurePalette.lavender,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  tryOnButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  lookSecondaryActions: {
    flexDirection: "row",
    gap: 10
  },
  refineChipRow: {
    marginTop: 16,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  recommendationContent: {
    paddingTop: 56,
    paddingBottom: 40
  },
  detailHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  recommendationTitleBlock: {
    marginTop: 20,
    marginBottom: 20
  },
  recommendationEyebrowRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 8
  },
  recommendationTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 28,
    lineHeight: 32,
    letterSpacing: -0.48,
    color: featurePalette.foreground
  },
  recommendationQuote: {
    marginTop: 6,
    fontFamily: fontFamilies.serifRegularItalic,
    fontSize: 14,
    lineHeight: 20,
    color: featurePalette.muted
  },
  recommendationItemsRail: {
    marginBottom: 24
  },
  recommendationItemCard: {
    width: 130,
    marginRight: 12
  },
  recommendationItemFrame: {
    aspectRatio: 3 / 4,
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 8
  },
  recommendationItemImage: {
    width: "100%",
    height: "100%"
  },
  scoreCard: {
    borderRadius: 24,
    padding: 20,
    backgroundColor: "#FFFFFF",
    marginBottom: 24
  },
  scoreCardRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12
  },
  scoreCardValue: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 32,
    lineHeight: 36,
    color: featurePalette.foreground
  },
  recommendationSection: {
    marginBottom: 24
  },
  preferenceTitle: {
    marginBottom: 12,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  altStack: {
    gap: 12
  },
  altCard: {
    borderRadius: 18,
    padding: 16,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    gap: 12
  },
  altCopy: {
    flex: 1
  }
});
