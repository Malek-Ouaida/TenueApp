import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { router, useLocalSearchParams, type Href } from "expo-router";
import { useEffect, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { fontFamilies } from "../theme";
import { AppText } from "../ui";
import { CLOSET_ITEMS, getClosetItemById } from "../lib/reference/wardrobe";
import { launchLibraryForImages } from "../media/picker";
import { featurePalette, featureShadows } from "../theme/feature";
import { Chip, LoadingState, FeatureScreen, StickyActionBar, SurfaceIconButton } from "../ui/feature-surfaces";

type Verdict = "buy" | "consider" | "skip";

type ShopProduct = {
  id: number;
  name: string;
  brand: string;
  price: string;
  image: string;
  url: string;
};

type DetectedItem = {
  id: number;
  name: string;
  category: string;
  x: number;
  y: number;
  exactMatch: ShopProduct | null;
  similar: ShopProduct[];
};

const SHOULD_BUY_RESULT = {
  verdict: "buy" as Verdict,
  headline: "Buy it",
  subtitle: "This fits well with your wardrobe.",
  explanation:
    "This item adds a clean, versatile layer that integrates well with your current wardrobe. It opens up multiple outfit combinations and fills a gap you currently have in transitional layering pieces.",
  versatilityCount: 6,
  gapText: "This fills a gap in your wardrobe",
  similarIds: [1, 3],
  stylePreview: [
    {
      title: "Polished weekend look",
      itemIds: [2, 6, 8]
    }
  ]
} as const;

const SHOP_PRODUCTS: ShopProduct[] = [
  {
    id: 1,
    name: "Leather Biker Jacket",
    brand: "AllSaints",
    price: "$498",
    image: "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=200&h=250&fit=crop",
    url: "#"
  },
  {
    id: 2,
    name: "Classic Moto Jacket",
    brand: "Acne Studios",
    price: "$1,800",
    image: "https://images.unsplash.com/photo-1520975954732-35dd22299614?w=200&h=250&fit=crop",
    url: "#"
  },
  {
    id: 3,
    name: "Oversized Leather Jacket",
    brand: "Zara",
    price: "$149",
    image: "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=200&h=250&fit=crop",
    url: "#"
  },
  {
    id: 4,
    name: "Slim Fit Dark Jeans",
    brand: "A.P.C.",
    price: "$210",
    image: "https://images.unsplash.com/photo-1542272604-787c3835535d?w=200&h=250&fit=crop",
    url: "#"
  },
  {
    id: 5,
    name: "Straight Leg Denim",
    brand: "Levi's",
    price: "$98",
    image: "https://images.unsplash.com/photo-1582552938357-32b906df40cb?w=200&h=250&fit=crop",
    url: "#"
  },
  {
    id: 6,
    name: "Chelsea Boots",
    brand: "Common Projects",
    price: "$575",
    image: "https://images.unsplash.com/photo-1638247025967-b4e38f787b76?w=200&h=250&fit=crop",
    url: "#"
  },
  {
    id: 7,
    name: "Suede Chelsea Boot",
    brand: "COS",
    price: "$190",
    image: "https://images.unsplash.com/photo-1608256246200-53e635b5b65f?w=200&h=250&fit=crop",
    url: "#"
  }
];

const DETECTED_ITEMS: DetectedItem[] = [
  {
    id: 1,
    name: "Black leather jacket",
    category: "Outerwear",
    x: 50,
    y: 30,
    exactMatch: SHOP_PRODUCTS[0] ?? null,
    similar: [SHOP_PRODUCTS[1], SHOP_PRODUCTS[2]].filter(Boolean) as ShopProduct[]
  },
  {
    id: 2,
    name: "Dark slim jeans",
    category: "Bottoms",
    x: 48,
    y: 65,
    exactMatch: null,
    similar: [SHOP_PRODUCTS[3], SHOP_PRODUCTS[4]].filter(Boolean) as ShopProduct[]
  },
  {
    id: 3,
    name: "Chelsea boots",
    category: "Shoes",
    x: 45,
    y: 88,
    exactMatch: SHOP_PRODUCTS[5] ?? null,
    similar: [SHOP_PRODUCTS[6]].filter(Boolean) as ShopProduct[]
  }
];

const DETECTED_BOXES = [
  { id: 1, label: "Blazer", confidence: 96, top: "15%", left: "20%", width: "60%", height: "35%" },
  { id: 2, label: "Trousers", confidence: 94, top: "52%", left: "25%", width: "50%", height: "35%" },
  { id: 3, label: "Shoes", confidence: 89, top: "88%", left: "30%", width: "40%", height: "10%" }
] as const;

export function ShouldIBuyScreen() {
  const [imageUri, setImageUri] = useState<string | null>(null);

  async function handleUpload() {
    const [uri] = await launchLibraryForImages();
    if (uri) {
      setImageUri(uri);
    }
  }

  function handleSubmit() {
    if (!imageUri) {
      return;
    }

    router.push(({
      pathname: "/should-i-buy/results",
      params: { imageUri }
    } as unknown) as Href);
  }

  return (
    <ImageUploadFlow
      buttonLabel="Analyze this item"
      imageUri={imageUri}
      onBack={() => router.back()}
      onClear={() => setImageUri(null)}
      onPrimary={handleSubmit}
      onUpload={() => void handleUpload()}
      subtitle="Snap or upload an item you're considering"
      title="Should I buy this?"
      uploadSubtitle="Tap to upload or take a photo"
    />
  );
}

export function ShouldIBuyResultsScreen() {
  const params = useLocalSearchParams<{ imageUri?: string }>();
  const imageUri = typeof params.imageUri === "string" ? params.imageUri : null;
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 2600);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <LoadingState
        backgroundUri={imageUri}
        icon={<Feather color={featurePalette.foreground} name="shopping-bag" size={28} />}
        subtitle="Comparing with your closet"
        title="Analyzing this piece"
      />
    );
  }

  const verdictStyle = getVerdictStyle(SHOULD_BUY_RESULT.verdict);
  const similarItems = SHOULD_BUY_RESULT.similarIds
    .map((id) => getClosetItemById(id))
    .filter((item): item is NonNullable<typeof item> => item !== null);

  return (
    <ScrollView bounces={false} contentContainerStyle={styles.resultsContent} showsVerticalScrollIndicator={false} style={styles.fullScreen}>
      <View style={styles.resultsHero}>
        {imageUri ? <Image contentFit="cover" source={{ uri: imageUri }} style={styles.resultsHeroImage} /> : null}
        <LinearGradient
          colors={["transparent", "rgba(250,249,247,0.12)", featurePalette.background]}
          locations={[0, 0.65, 1]}
          style={StyleSheet.absoluteFillObject}
        />
        <View style={styles.resultsHeroTop}>
          <SurfaceIconButton
            icon={<Feather color={featurePalette.foreground} name="arrow-left" size={20} />}
            onPress={() => router.back()}
            translucent
          />
        </View>
      </View>

      <View style={[styles.verdictCard, featureShadows.md, verdictStyle.card]}>
        <View style={styles.verdictHeader}>
          <View style={[styles.verdictIcon, verdictStyle.iconWrap]}>
            <Feather color={verdictStyle.iconColor} name={verdictStyle.icon} size={20} />
          </View>
          <AppText style={[styles.verdictTitle, { color: verdictStyle.iconColor }]}>{SHOULD_BUY_RESULT.headline}</AppText>
        </View>
        <AppText style={styles.verdictSubtitle}>{SHOULD_BUY_RESULT.subtitle}</AppText>
      </View>

      <View style={styles.sectionPad}>
        <AppText style={styles.sectionEyebrow}>Key Insights</AppText>
        <View style={styles.cardStack}>
          <InsightRow
            icon="layers"
            title={`Pairs with ${SHOULD_BUY_RESULT.versatilityCount} items`}
            subtitle="in your closet"
          />
          <InsightRow
            icon="puzzle"
            title={SHOULD_BUY_RESULT.gapText}
            subtitle=""
          />
        </View>
      </View>

      {similarItems.length ? (
        <View style={styles.sectionPad}>
          <AppText style={styles.sectionEyebrow}>Similar in your closet</AppText>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {similarItems.map((item) => (
              <View key={item.id} style={styles.railCard}>
                <View style={styles.railCardImageFrame}>
                  <Image contentFit="cover" source={item.image} style={styles.railCardImage} />
                </View>
                <AppText style={styles.railCardTitle}>{item.title}</AppText>
                <AppText style={styles.railCardMeta}>{item.brand}</AppText>
              </View>
            ))}
          </ScrollView>
        </View>
      ) : null}

      <View style={styles.sectionPad}>
        <View style={[styles.textCard, featureShadows.sm]}>
          <View style={styles.textCardHeader}>
            <MaterialCommunityIcons color={featurePalette.muted} name="star-four-points" size={14} />
            <AppText style={styles.sectionEyebrow}>Our take</AppText>
          </View>
          <AppText style={styles.textCardCopy}>{SHOULD_BUY_RESULT.explanation}</AppText>
        </View>
      </View>

      <View style={styles.sectionPad}>
        <AppText style={styles.sectionEyebrow}>How you'd wear it</AppText>
        {SHOULD_BUY_RESULT.stylePreview.map((outfit) => {
          const items = outfit.itemIds
            .map((id) => getClosetItemById(id))
            .filter((item): item is NonNullable<typeof item> => item !== null);

          return (
            <View key={outfit.title} style={[styles.previewCard, featureShadows.sm]}>
              <AppText style={styles.previewTitle}>{outfit.title}</AppText>
              <View style={styles.previewItems}>
                {items.map((item) => (
                  <Image key={item.id} contentFit="cover" source={item.image} style={styles.previewItemImage} />
                ))}
              </View>
            </View>
          );
        })}
      </View>

      <View style={styles.sectionPad}>
        <PrimaryPillButton icon="bookmark" label="Save for later" onPress={() => {}} />
        <View style={styles.buttonSpacer} />
        <SecondaryPillButton icon="shirt" label="Show how to style it" onPress={() => {}} />
      </View>
    </ScrollView>
  );
}

export function CandidateComparisonScreen() {
  const similarOwned = CLOSET_ITEMS.filter((item) => item.category === "outerwear").slice(0, 3);

  return (
    <FeatureScreen contentContainerStyle={styles.screenContent}>
      <SurfaceIconButton
        icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
        onPress={() => router.back()}
      />

      <View style={styles.headerBlock}>
        <View style={styles.sparkleRow}>
          <MaterialCommunityIcons color={featurePalette.muted} name="star-four-points" size={14} />
          <AppText style={styles.sectionEyebrow}>Closet comparison</AppText>
        </View>
        <AppText style={styles.compareTitle}>How it compares to{"\n"}what you own</AppText>
      </View>

      <CompareSection label="Considering">
        <View style={[styles.compareCard, featureShadows.sm]}>
          <View style={styles.compareImageFrame}>
            <Image contentFit="cover" source={CLOSET_ITEMS[0]?.image} style={styles.compareImage} />
          </View>
          <View style={styles.compareCopy}>
            <AppText style={styles.compareItemTitle}>Wool Blend Blazer</AppText>
            <AppText style={styles.compareItemMeta}>COS · $175</AppText>
          </View>
        </View>
      </CompareSection>

      <CompareSection label={`Similar in your closet (${similarOwned.length})`}>
        <View style={styles.compareStack}>
          {similarOwned.map((item) => (
            <Pressable
              key={item.id}
              onPress={() => router.push(`/closet/${item.id}`)}
              style={({ pressed }) => [styles.compareOwnedRow, featureShadows.sm, pressed ? styles.buttonPressed : null]}
            >
              <View style={styles.compareOwnedImageWrap}>
                <Image contentFit="cover" source={item.image} style={styles.compareOwnedImage} />
              </View>
              <View style={styles.compareCopy}>
                <AppText style={styles.compareItemTitle}>{item.title}</AppText>
                <AppText style={styles.compareItemMeta}>{item.color} · Worn {item.timesWorn}×</AppText>
              </View>
            </Pressable>
          ))}
        </View>
      </CompareSection>

      <CompareSection label="Verdict">
        <View style={[styles.textCard, featureShadows.sm]}>
          <AppText style={styles.textCardCopy}>
            You already own {similarOwned.length} similar pieces. Consider if this adds something new to your wardrobe.
          </AppText>
        </View>
      </CompareSection>
    </FeatureScreen>
  );
}

export function ShopTheLookScreen() {
  const [imageUri, setImageUri] = useState<string | null>(null);

  async function handleUpload() {
    const [uri] = await launchLibraryForImages();
    if (uri) {
      setImageUri(uri);
    }
  }

  function handleSubmit() {
    if (!imageUri) {
      return;
    }

    router.push(({
      pathname: "/shop-the-look/results",
      params: { imageUri }
    } as unknown) as Href);
  }

  return (
    <ImageUploadFlow
      buttonLabel="Find these items"
      imageUri={imageUri}
      onBack={() => router.back()}
      onClear={() => setImageUri(null)}
      onPrimary={handleSubmit}
      onUpload={() => void handleUpload()}
      subtitle="Upload a look you like"
      title="Shop the look"
      uploadSubtitle="Snap or upload an outfit image"
    />
  );
}

export function DetectedItemsScreen() {
  const params = useLocalSearchParams<{ imageUri?: string }>();
  const [selectedIds, setSelectedIds] = useState<number[]>([1]);
  const imageUri = typeof params.imageUri === "string" ? params.imageUri : null;

  function toggle(id: number) {
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  return (
    <FeatureScreen contentContainerStyle={styles.screenContent}>
      <View style={styles.topRow}>
        <SurfaceIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
          onPress={() => router.back()}
        />
      </View>

      <View style={styles.headerBlock}>
        <AppText style={styles.detailHeaderTitle}>We found these</AppText>
        <AppText style={styles.pageSubtitle}>Choose what you'd like to shop</AppText>
      </View>

      <View style={styles.detectedFrame}>
        {imageUri ? <Image contentFit="cover" source={{ uri: imageUri }} style={styles.detectedFrameImage} /> : null}
        {DETECTED_BOXES.map((item) => {
          const selected = selectedIds.includes(item.id);
          return (
            <Pressable
              key={item.id}
              onPress={() => toggle(item.id)}
              style={[
                styles.detectedBox,
                {
                  top: item.top,
                  left: item.left,
                  width: item.width,
                  height: item.height
                },
                selected ? styles.detectedBoxActive : styles.detectedBoxIdle
              ]}
            >
              <View style={[styles.detectedBadge, selected ? styles.detectedBadgeActive : styles.detectedBadgeIdle]}>
                <AppText style={[styles.detectedBadgeLabel, selected ? styles.detectedBadgeLabelActive : null]}>
                  {item.label}
                </AppText>
              </View>
              {selected ? (
                <View style={styles.detectedCheck}>
                  <Feather color="#FFFFFF" name="check" size={12} />
                </View>
              ) : null}
            </Pressable>
          );
        })}
      </View>

      <AppText style={styles.pageSubtitle}>
        {selectedIds.length} item{selectedIds.length !== 1 ? "s" : ""} selected
      </AppText>

      <View style={styles.footerPad}>
        <PrimaryPillButton
          icon="search"
          label="Find these pieces"
          onPress={() =>
            router.push(
              ({
                pathname: "/shop-the-look/results",
                params: {
                  imageUri: imageUri ?? "",
                  selected: selectedIds.join(",")
                }
              } as unknown) as Href
            )
          }
        />
      </View>
    </FeatureScreen>
  );
}

export function ShopTheLookResultsScreen() {
  const params = useLocalSearchParams<{ imageUri?: string }>();
  const imageUri = typeof params.imageUri === "string" ? params.imageUri : null;
  const [loading, setLoading] = useState(true);
  const [showAllItems, setShowAllItems] = useState(false);
  const [selectedItem, setSelectedItem] = useState<DetectedItem | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(false);
      setSelectedItem(DETECTED_ITEMS[0] ?? null);
    }, 2800);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <LoadingState
        backgroundUri={imageUri}
        icon={<MaterialCommunityIcons color={featurePalette.foreground} name="line-scan" size={28} />}
        subtitle="Identifying items and finding matches"
        title="Analyzing the look"
      />
    );
  }

  return (
    <ScrollView bounces={false} contentContainerStyle={styles.shopResultsContent} showsVerticalScrollIndicator={false} style={styles.fullScreen}>
      <View style={styles.shopResultsHero}>
        {imageUri ? <Image contentFit="cover" source={{ uri: imageUri }} style={styles.shopResultsHeroImage} /> : null}
        <LinearGradient
          colors={["transparent", "transparent", "rgba(250,249,247,0.88)"]}
          locations={[0, 0.6, 1]}
          style={StyleSheet.absoluteFillObject}
        />

        <View style={styles.shopResultsTopBar}>
          <SurfaceIconButton
            icon={<Feather color={featurePalette.foreground} name="arrow-left" size={20} />}
            onPress={() => router.back()}
            translucent
          />
          <Pressable onPress={() => setShowAllItems((current) => !current)} style={styles.foundItemsButton}>
            <AppText style={styles.foundItemsLabel}>{DETECTED_ITEMS.length} items found</AppText>
            <Feather color={featurePalette.foreground} name="chevron-down" size={16} />
          </Pressable>
        </View>

        {DETECTED_ITEMS.map((item) => {
          const active = selectedItem?.id === item.id;
          return (
            <Pressable
              key={item.id}
              onPress={() => setSelectedItem(item)}
              style={[
                styles.hotspot,
                {
                  left: `${item.x}%`,
                  top: `${item.y}%`
                },
                active ? styles.hotspotActive : null
              ]}
            >
              <View style={[styles.hotspotInner, active ? styles.hotspotInnerActive : null]}>
                <View style={[styles.hotspotDot, active ? styles.hotspotDotActive : null]} />
              </View>
              {active ? (
                <View style={styles.hotspotLabel}>
                  <AppText style={styles.hotspotLabelText}>{item.name}</AppText>
                </View>
              ) : null}
            </Pressable>
          );
        })}
      </View>

      {showAllItems ? (
        <View style={styles.dropdownWrap}>
          <View style={[styles.dropdownCard, featureShadows.md]}>
            {DETECTED_ITEMS.map((item) => (
              <Pressable
                key={item.id}
                onPress={() => {
                  setSelectedItem(item);
                  setShowAllItems(false);
                }}
                style={({ pressed }) => [styles.dropdownRow, pressed ? styles.buttonPressed : null]}
              >
                <View style={styles.dropdownBadge}>
                  <AppText style={styles.dropdownBadgeLabel}>{item.id}</AppText>
                </View>
                <View style={styles.dropdownCopy}>
                  <AppText style={styles.dropdownTitle}>{item.name}</AppText>
                  <AppText style={styles.dropdownSubtitle}>{item.category}</AppText>
                </View>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}

      {selectedItem ? (
        <View style={styles.sectionPad}>
          <View style={styles.selectedHeader}>
            <View style={styles.categoryBadge}>
              <AppText style={styles.categoryBadgeLabel}>{selectedItem.category}</AppText>
            </View>
            <AppText style={styles.selectedItemTitle}>{selectedItem.name}</AppText>
          </View>

          {selectedItem.exactMatch ? (
            <View style={styles.exactSection}>
              <AppText style={styles.sectionEyebrow}>Exact match</AppText>
              <View style={[styles.exactCard, featureShadows.md]}>
                <Image contentFit="cover" source={{ uri: selectedItem.exactMatch.image }} style={styles.exactImage} />
                <View style={styles.exactCopy}>
                  <View>
                    <AppText style={styles.exactBrand}>{selectedItem.exactMatch.brand}</AppText>
                    <AppText style={styles.exactName}>{selectedItem.exactMatch.name}</AppText>
                  </View>
                  <View style={styles.exactFooter}>
                    <AppText style={styles.exactPrice}>{selectedItem.exactMatch.price}</AppText>
                    <View style={styles.exactActions}>
                      <CircleIconButton icon="bookmark" onPress={() => {}} />
                      <CircleIconButton
                        icon="external-link"
                        onPress={() =>
                          router.push(
                            ({
                              pathname: `/shop-the-look/product/${selectedItem.exactMatch?.id ?? 1}`,
                              params: { productId: String(selectedItem.exactMatch?.id ?? 1) }
                            } as unknown) as Href
                          )
                        }
                        solid
                      />
                    </View>
                  </View>
                </View>
              </View>
            </View>
          ) : null}

          {selectedItem.similar.length ? (
            <View>
              <AppText style={styles.sectionEyebrow}>Similar pieces</AppText>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {selectedItem.similar.map((product) => (
                  <Pressable
                    key={product.id}
                    onPress={() =>
                      router.push(
                        ({
                          pathname: `/shop-the-look/product/${product.id}`,
                          params: { productId: String(product.id) }
                        } as unknown) as Href
                      )
                    }
                    style={({ pressed }) => [styles.productCard, featureShadows.sm, pressed ? styles.buttonPressed : null]}
                  >
                    <Image contentFit="cover" source={{ uri: product.image }} style={styles.productCardImage} />
                    <View style={styles.productCardBody}>
                      <AppText style={styles.exactBrand}>{product.brand}</AppText>
                      <AppText style={styles.productCardName}>{product.name}</AppText>
                      <View style={styles.productCardFooter}>
                        <AppText style={styles.productCardPrice}>{product.price}</AppText>
                        <View style={styles.productCardAction}>
                          <Feather color={featurePalette.foreground} name="external-link" size={14} />
                        </View>
                      </View>
                    </View>
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          ) : null}
        </View>
      ) : null}
    </ScrollView>
  );
}

export function ProductDetailScreen() {
  const params = useLocalSearchParams<{ productId?: string }>();
  const [saved, setSaved] = useState(false);
  const productId = Number(params.productId ?? "1");
  const product = SHOP_PRODUCTS.find((item) => item.id === productId) ?? SHOP_PRODUCTS[0]!;

  return (
    <View style={styles.fullScreen}>
      <View style={styles.productHero}>
        <Image contentFit="cover" source={{ uri: product.image }} style={styles.productHeroImage} />
        <View style={styles.productHeroTop}>
          <SurfaceIconButton
            icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
            onPress={() => router.back()}
            translucent
          />
          <SurfaceIconButton
            icon={<Feather color={saved ? "#F87171" : featurePalette.foreground} name="heart" size={18} />}
            onPress={() => setSaved((current) => !current)}
            translucent
          />
        </View>
        <View style={styles.matchBadge}>
          <MaterialCommunityIcons color={featurePalette.foreground} name="star-four-points" size={14} />
          <AppText style={styles.matchBadgeLabel}>94% match</AppText>
        </View>
      </View>

      <ScrollView bounces={false} contentContainerStyle={styles.productContent} showsVerticalScrollIndicator={false}>
        <AppText style={styles.exactBrand}>{product.brand}</AppText>
        <AppText style={styles.productTitle}>{product.name}</AppText>
        <AppText style={styles.productPrice}>{product.price}</AppText>

        <AppText style={styles.productDescription}>
          A refined single-breasted blazer in a soft wool blend. Notch lapels, flap pockets, and a relaxed fit that drapes beautifully.
        </AppText>

        <View style={styles.productDetailSection}>
          <AppText style={styles.sectionEyebrow}>Details</AppText>
          <View style={styles.detailsChipRow}>
            {["Wool blend", "Relaxed fit", "Single-breasted", "Notch lapels"].map((item) => (
              <Chip key={item} active={false} label={item} onPress={() => {}} />
            ))}
          </View>
        </View>

        <View style={[styles.sourceCard, featureShadows.sm]}>
          <View>
            <AppText style={styles.dropdownSubtitle}>Available at</AppText>
            <AppText style={styles.sourceLabel}>cos.com</AppText>
          </View>
          <Feather color={featurePalette.muted} name="external-link" size={16} />
        </View>
      </ScrollView>

      <StickyActionBar>
        <View style={styles.productFooterRow}>
          <Pressable onPress={() => setSaved((current) => !current)} style={({ pressed }) => [styles.squareSaveButton, pressed ? styles.buttonPressed : null]}>
            <Feather color={saved ? "#F87171" : featurePalette.foreground} name="heart" size={18} />
          </Pressable>
          <PrimaryPillButton icon="external-link" label="Visit store" onPress={() => {}} />
        </View>
      </StickyActionBar>
    </View>
  );
}

function ImageUploadFlow({
  buttonLabel,
  imageUri,
  onBack,
  onClear,
  onPrimary,
  onUpload,
  subtitle,
  title,
  uploadSubtitle
}: {
  buttonLabel: string;
  imageUri: string | null;
  onBack: () => void;
  onClear: () => void;
  onPrimary: () => void;
  onUpload: () => void;
  subtitle: string;
  title: string;
  uploadSubtitle: string;
}) {
  return (
    <View style={styles.fullScreen}>
      <FeatureScreen contentContainerStyle={styles.flowScreenContent} style={styles.fullScreen}>
        <SurfaceIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={20} />}
          onPress={onBack}
        />

        <View style={styles.headerBlock}>
          <AppText style={styles.flowTitle}>{title}</AppText>
          <AppText style={styles.pageSubtitle}>{subtitle}</AppText>
        </View>

        {imageUri ? (
          <View style={styles.uploadPreview}>
            <Image contentFit="cover" source={{ uri: imageUri }} style={styles.uploadPreviewImage} />
            <Pressable onPress={onClear} style={styles.uploadPreviewClear}>
              <Feather color="#FFFFFF" name="x" size={16} />
            </Pressable>
          </View>
        ) : (
          <Pressable onPress={onUpload} style={({ pressed }) => [styles.dropzone, pressed ? styles.buttonPressed : null]}>
            <View style={styles.dropzoneIcon}>
              <Feather color={featurePalette.muted} name="image" size={26} />
            </View>
            <AppText style={styles.dropzoneTitle}>Add a photo</AppText>
            <AppText style={styles.dropzoneSubtitle}>{uploadSubtitle}</AppText>
          </Pressable>
        )}
      </FeatureScreen>

      <StickyActionBar>
        <PrimaryPillButton disabled={!imageUri} label={buttonLabel} onPress={onPrimary} />
      </StickyActionBar>
    </View>
  );
}

function InsightRow({
  icon,
  subtitle,
  title
}: {
  icon: "layers" | "puzzle";
  subtitle: string;
  title: string;
}) {
  const iconName = icon === "layers" ? "layers" : "grid";

  return (
    <View style={[styles.insightRowCard, featureShadows.sm]}>
      <View style={styles.insightRowIcon}>
        <Feather color={featurePalette.foreground} name={iconName} size={18} />
      </View>
      <View style={styles.compareCopy}>
        <AppText style={styles.compareItemTitle}>{title}</AppText>
        {subtitle ? <AppText style={styles.compareItemMeta}>{subtitle}</AppText> : null}
      </View>
    </View>
  );
}

function CompareSection({
  children,
  label
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <View style={styles.compareSection}>
      <AppText style={styles.sectionEyebrow}>{label}</AppText>
      {children}
    </View>
  );
}

function PrimaryPillButton({
  icon,
  label,
  onPress,
  disabled
}: {
  icon?: keyof typeof Feather.glyphMap;
  label: string;
  onPress: () => void;
  disabled?: boolean;
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
      {icon ? <Feather color={disabled ? featurePalette.muted : "#FFFFFF"} name={icon} size={16} /> : null}
      <AppText style={[styles.primaryButtonLabel, disabled ? styles.primaryButtonLabelDisabled : null]}>{label}</AppText>
    </Pressable>
  );
}

function SecondaryPillButton({
  icon,
  label,
  onPress
}: {
  icon: "shirt" | "bookmark";
  label: string;
  onPress: () => void;
}) {
  const iconName = icon === "shirt" ? "shopping-bag" : "bookmark";

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.secondaryButton, pressed ? styles.buttonPressed : null]}>
      <Feather color={featurePalette.foreground} name={iconName} size={16} />
      <AppText style={styles.secondaryButtonLabel}>{label}</AppText>
    </Pressable>
  );
}

function CircleIconButton({
  icon,
  onPress,
  solid
}: {
  icon: keyof typeof Feather.glyphMap;
  onPress: () => void;
  solid?: boolean;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.circleIconButton, solid ? styles.circleIconButtonSolid : styles.circleIconButtonSoft, pressed ? styles.buttonPressed : null]}>
      <Feather color={solid ? "#FFFFFF" : featurePalette.foreground} name={icon} size={14} />
    </Pressable>
  );
}

function getVerdictStyle(verdict: Verdict) {
  if (verdict === "buy") {
    return {
      card: { backgroundColor: "rgba(16,185,129,0.1)", borderColor: "rgba(16,185,129,0.2)" },
      iconWrap: { backgroundColor: "rgba(16,185,129,0.1)" },
      icon: "check" as const,
      iconColor: "#10B981"
    };
  }

  if (verdict === "consider") {
    return {
      card: { backgroundColor: "rgba(245,158,11,0.1)", borderColor: "rgba(245,158,11,0.2)" },
      iconWrap: { backgroundColor: "rgba(245,158,11,0.1)" },
      icon: "alert-triangle" as const,
      iconColor: "#F59E0B"
    };
  }

  return {
    card: { backgroundColor: "rgba(239,68,68,0.1)", borderColor: "rgba(239,68,68,0.2)" },
    iconWrap: { backgroundColor: "rgba(239,68,68,0.1)" },
    icon: "x-circle" as const,
    iconColor: "#EF4444"
  };
}

const styles = StyleSheet.create({
  fullScreen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  screenContent: {
    paddingTop: 56,
    paddingHorizontal: 24,
    paddingBottom: 40
  },
  flowScreenContent: {
    paddingTop: 56,
    paddingHorizontal: 24,
    paddingBottom: 140
  },
  resultsContent: {
    paddingBottom: 40
  },
  buttonPressed: {
    opacity: 0.9,
    transform: [{ scale: 0.98 }]
  },
  topRow: {
    marginBottom: 8
  },
  headerBlock: {
    marginTop: 24,
    marginBottom: 20
  },
  sparkleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 8
  },
  flowTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 28,
    lineHeight: 34,
    letterSpacing: -0.48,
    color: featurePalette.foreground
  },
  detailHeaderTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 26,
    lineHeight: 32,
    letterSpacing: -0.48,
    color: featurePalette.foreground
  },
  pageSubtitle: {
    marginTop: 6,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 20,
    color: featurePalette.muted
  },
  dropzone: {
    aspectRatio: 3 / 4,
    borderRadius: 24,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: featurePalette.border,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  dropzoneIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: featurePalette.background,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 14
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
  primaryButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    height: 56,
    borderRadius: 28,
    backgroundColor: featurePalette.foreground
  },
  primaryButtonDisabled: {
    backgroundColor: "#D9DEE7"
  },
  primaryButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20,
    color: "#FFFFFF"
  },
  primaryButtonLabelDisabled: {
    color: featurePalette.muted
  },
  secondaryButton: {
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
  secondaryButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  buttonSpacer: {
    height: 12
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
  verdictCard: {
    marginHorizontal: 24,
    marginTop: -64,
    padding: 24,
    borderRadius: 24,
    borderWidth: 1
  },
  verdictHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 12
  },
  verdictIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center"
  },
  verdictTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 32,
    lineHeight: 36,
    letterSpacing: -0.48
  },
  verdictSubtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  sectionPad: {
    paddingHorizontal: 24,
    marginTop: 24
  },
  sectionEyebrow: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  cardStack: {
    gap: 12,
    marginTop: 14
  },
  insightRowCard: {
    borderRadius: 20,
    padding: 18,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    gap: 14
  },
  insightRowIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(110, 197, 170, 0.25)",
    alignItems: "center",
    justifyContent: "center"
  },
  railCard: {
    width: 120,
    marginRight: 12
  },
  railCardImageFrame: {
    width: 120,
    height: 150,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 8
  },
  railCardImage: {
    width: "100%",
    height: "100%"
  },
  railCardTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  railCardMeta: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.muted
  },
  textCard: {
    borderRadius: 24,
    padding: 24,
    backgroundColor: "#FFFFFF"
  },
  textCardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 12
  },
  textCardCopy: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 24,
    color: featurePalette.muted
  },
  previewCard: {
    marginTop: 14,
    borderRadius: 24,
    padding: 20,
    backgroundColor: "#FFFFFF"
  },
  previewTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground,
    marginBottom: 12
  },
  previewItems: {
    flexDirection: "row",
    gap: 8
  },
  previewItemImage: {
    width: 56,
    height: 56,
    borderRadius: 16
  },
  compareTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 26,
    lineHeight: 32,
    letterSpacing: -0.48,
    color: featurePalette.foreground
  },
  compareSection: {
    marginTop: 24
  },
  compareCard: {
    marginTop: 12,
    borderRadius: 24,
    padding: 16,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    gap: 16
  },
  compareImageFrame: {
    width: 64,
    height: 80,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  compareImage: {
    width: "100%",
    height: "100%"
  },
  compareCopy: {
    flex: 1
  },
  compareItemTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  compareItemMeta: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  compareStack: {
    marginTop: 12,
    gap: 12
  },
  compareOwnedRow: {
    borderRadius: 20,
    padding: 16,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    gap: 14
  },
  compareOwnedImageWrap: {
    width: 48,
    height: 48,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  compareOwnedImage: {
    width: "100%",
    height: "100%"
  },
  detectedFrame: {
    position: "relative",
    aspectRatio: 3 / 4,
    borderRadius: 24,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 18
  },
  detectedFrameImage: {
    width: "100%",
    height: "100%"
  },
  detectedBox: {
    position: "absolute",
    borderWidth: 2,
    borderRadius: 16
  },
  detectedBoxActive: {
    borderColor: featurePalette.foreground,
    backgroundColor: "rgba(15,23,42,0.08)"
  },
  detectedBoxIdle: {
    borderColor: "rgba(255,255,255,0.45)",
    backgroundColor: "rgba(255,255,255,0.05)"
  },
  detectedBadge: {
    position: "absolute",
    top: -12,
    left: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999
  },
  detectedBadgeActive: {
    backgroundColor: featurePalette.foreground
  },
  detectedBadgeIdle: {
    backgroundColor: "rgba(255,255,255,0.82)"
  },
  detectedBadgeLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.foreground
  },
  detectedBadgeLabelActive: {
    color: "#FFFFFF"
  },
  detectedCheck: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: featurePalette.foreground,
    alignItems: "center",
    justifyContent: "center"
  },
  footerPad: {
    marginTop: 24
  },
  shopResultsContent: {
    paddingBottom: 40
  },
  shopResultsHero: {
    position: "relative",
    width: "100%",
    aspectRatio: 3 / 4,
    backgroundColor: featurePalette.secondary
  },
  shopResultsHeroImage: {
    width: "100%",
    height: "100%"
  },
  shopResultsTopBar: {
    position: "absolute",
    top: 56,
    left: 24,
    right: 24,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  foundItemsButton: {
    height: 36,
    paddingHorizontal: 14,
    borderRadius: 18,
    backgroundColor: "rgba(255,255,255,0.82)",
    flexDirection: "row",
    alignItems: "center",
    gap: 6
  },
  foundItemsLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  hotspot: {
    position: "absolute",
    transform: [{ translateX: -16 }, { translateY: -16 }]
  },
  hotspotActive: {
    zIndex: 2
  },
  hotspotInner: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.92)",
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.92)"
  },
  hotspotInnerActive: {
    backgroundColor: featurePalette.foreground,
    borderColor: featurePalette.foreground
  },
  hotspotDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: featurePalette.foreground
  },
  hotspotDotActive: {
    backgroundColor: "#FFFFFF"
  },
  hotspotLabel: {
    position: "absolute",
    top: 36,
    alignSelf: "center",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: featurePalette.foreground
  },
  hotspotLabelText: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    color: "#FFFFFF"
  },
  dropdownWrap: {
    paddingHorizontal: 24,
    marginTop: -16,
    zIndex: 2
  },
  dropdownCard: {
    borderRadius: 20,
    padding: 12,
    backgroundColor: "#FFFFFF"
  },
  dropdownRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 10,
    borderRadius: 16
  },
  dropdownBadge: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  dropdownBadgeLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  dropdownCopy: {
    flex: 1
  },
  dropdownTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  dropdownSubtitle: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  selectedHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 16
  },
  categoryBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: featurePalette.secondary
  },
  categoryBadgeLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  selectedItemTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 17,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  exactSection: {
    marginBottom: 20
  },
  exactCard: {
    marginTop: 12,
    borderRadius: 22,
    padding: 16,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    gap: 16
  },
  exactImage: {
    width: 90,
    height: 110,
    borderRadius: 18
  },
  exactCopy: {
    flex: 1,
    justifyContent: "space-between"
  },
  exactBrand: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  exactName: {
    marginTop: 4,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  exactFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  exactPrice: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 18,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  exactActions: {
    flexDirection: "row",
    gap: 8
  },
  circleIconButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center"
  },
  circleIconButtonSoft: {
    backgroundColor: featurePalette.secondary
  },
  circleIconButtonSolid: {
    backgroundColor: featurePalette.foreground
  },
  productCard: {
    width: 150,
    marginRight: 12,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: "#FFFFFF"
  },
  productCardImage: {
    width: "100%",
    height: 180
  },
  productCardBody: {
    padding: 14
  },
  productCardName: {
    marginTop: 4,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  productCardFooter: {
    marginTop: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  productCardPrice: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  productCardAction: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  productHero: {
    position: "relative",
    aspectRatio: 3 / 4,
    backgroundColor: featurePalette.secondary
  },
  productHeroImage: {
    width: "100%",
    height: "100%"
  },
  productHeroTop: {
    position: "absolute",
    top: 56,
    left: 24,
    right: 24,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  matchBadge: {
    position: "absolute",
    left: 16,
    bottom: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.85)"
  },
  matchBadgeLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  productContent: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 160
  },
  productTitle: {
    marginTop: 2,
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 26,
    lineHeight: 30,
    letterSpacing: -0.4,
    color: featurePalette.foreground
  },
  productPrice: {
    marginTop: 8,
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 22,
    lineHeight: 26,
    color: featurePalette.foreground
  },
  productDescription: {
    marginTop: 20,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 24,
    color: featurePalette.muted
  },
  productDetailSection: {
    marginTop: 24
  },
  detailsChipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 12
  },
  sourceCard: {
    marginTop: 24,
    borderRadius: 20,
    padding: 16,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  sourceLabel: {
    marginTop: 2,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  productFooterRow: {
    flexDirection: "row",
    gap: 12
  },
  squareSaveButton: {
    width: 52,
    height: 52,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: featurePalette.border,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  }
});
