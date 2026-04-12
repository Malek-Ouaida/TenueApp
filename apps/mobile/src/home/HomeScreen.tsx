import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { router, useFocusEffect, type Href } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  Easing,
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { useAuth } from "../auth/provider";
import { selectSingleImage } from "../closet/upload";
import { useClosetInsights } from "../closet/insights";
import { useLookbookEntries } from "../lookbook/hooks";
import { useOutfits } from "../outfits/provider";
import { useProfile } from "../profile/hooks";
import { AppText } from "../ui";
import { FtueOverlay } from "../ui/feature-components";
import { supportsNativeAnimatedDriver } from "../lib/runtime";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";
import { useInsightOverview } from "./overview";
import { aiStylistPreview, homeFtueSteps } from "./reference";
import { hasSeenHomeFtue, markHomeFtueSeen } from "./storage";

function getGreeting() {
  const hour = new Date().getHours();

  if (hour < 12) {
    return "Good morning";
  }

  if (hour < 17) {
    return "Good afternoon";
  }

  return "Good evening";
}

function buildDisplayName(
  profileName: string | null | undefined,
  email: string | null | undefined
) {
  const trimmedProfileName = profileName?.trim();
  if (trimmedProfileName) {
    return trimmedProfileName;
  }

  const emailPrefix = email?.split("@")[0]?.split(/[._-]/)[0]?.trim();
  if (!emailPrefix) {
    return "You";
  }

  return emailPrefix.charAt(0).toUpperCase() + emailPrefix.slice(1);
}

function getInitials(name: string) {
  const segments = name.split(/\s+/).filter(Boolean);
  if (segments.length === 0) {
    return "T";
  }

  return segments
    .slice(0, 2)
    .map((segment) => segment.charAt(0).toUpperCase())
    .join("");
}

export default function HomeScreen() {
  const { logoutCurrentUser, session, user } = useAuth();
  const { setLogOutfitPhotoAsset } = useOutfits();
  const profile = useProfile({
    accessToken: session?.access_token,
    onUnauthorized: async () => {
      await logoutCurrentUser();
      router.replace("/login");
    }
  });
  const closetInsights = useClosetInsights(session?.access_token);
  const insightOverview = useInsightOverview(session?.access_token);
  const lookbook = useLookbookEntries(session?.access_token, { status: "published" }, 6);
  const [showFtue, setShowFtue] = useState(false);
  const [ftueStep, setFtueStep] = useState(0);
  const animations = useRef(Array.from({ length: 5 }, () => new Animated.Value(0))).current;
  const lookbookRefreshRef = useRef(lookbook.refresh);

  useEffect(() => {
    lookbookRefreshRef.current = lookbook.refresh;
  }, [lookbook.refresh]);

  useEffect(() => {
    Animated.stagger(
      40,
      animations.map((value) =>
        Animated.timing(value, {
          toValue: 1,
          duration: 360,
          easing: Easing.bezier(0.32, 0.72, 0, 1),
          useNativeDriver: supportsNativeAnimatedDriver
        })
      )
    ).start();
  }, [animations]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function maybeShowFtue() {
      const seen = await hasSeenHomeFtue();
      if (!active || seen) {
        return;
      }

      timer = setTimeout(() => {
        if (active) {
          setShowFtue(true);
        }
      }, 800);
    }

    void maybeShowFtue();

    return () => {
      active = false;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, []);

  useFocusEffect(
    useCallback(() => {
      void lookbookRefreshRef.current();
    }, [])
  );

  async function dismissFtue() {
    setShowFtue(false);
    setFtueStep(0);
    await markHomeFtueSeen();
  }

  async function advanceFtue() {
    if (ftueStep < homeFtueSteps.length - 1) {
      setFtueStep((current) => current + 1);
      return;
    }

    await dismissFtue();
  }

  async function handleHeroPhoto() {
    const asset = await selectSingleImage("camera");
    if (!asset) {
      return;
    }

    setLogOutfitPhotoAsset(asset);
    router.push(({ pathname: "/log-outfit", params: { mode: "photo" } } as unknown) as Href);
  }

  function push(href: string) {
    router.push(href as Href);
  }

  const animatedSections = useMemo(
    () =>
      animations.map((value) => ({
        opacity: value,
        transform: [
          {
            translateY: value.interpolate({
              inputRange: [0, 1],
              outputRange: [14, 0]
            })
          }
        ]
      })),
    [animations]
  );

  const displayName = buildDisplayName(profile.profile?.display_name, user?.email);
  const avatarInitials = getInitials(displayName);
  const closetCount = closetInsights.insights.totalItems;
  const wearLogCount = insightOverview.data?.all_time.total_wear_logs ?? 0;
  const streakCount = insightOverview.data?.streaks.current_streak_days ?? 0;
  const quickStats = [
    {
      label: "Closet items",
      value: `${closetCount}`,
      route: "/closet",
      background: "rgba(216, 235, 207, 0.35)",
      icon: <MaterialCommunityIcons color="#567848" name="hanger" size={18} />
    },
    {
      label: "Wear logs",
      value: `${wearLogCount}`,
      route: "/wear",
      background: "rgba(232, 219, 255, 0.35)",
      icon: <Feather color="#7658C3" name="camera" size={17} />
    },
    {
      label: "Day streak",
      value: `${streakCount}`,
      route: "/stats",
      background: "rgba(255, 210, 194, 0.4)",
      icon: <MaterialCommunityIcons color="#E46B34" name="fire" size={18} />
    }
  ] as const;
  const recentLooks = useMemo(
    () =>
      lookbook.items.slice(0, 4).map((entry, index) => ({
        id: entry.id,
        imageUrl: entry.primary_image?.url ?? null,
        background: ["#F7EFE6", "#F3F0FF", "#F0F7EF", "#FFF1EA"][index % 4],
        label:
          entry.title ??
          entry.caption ??
          entry.source_snapshot?.context ??
          "Saved look"
      })),
    [lookbook.items]
  );

  return (
    <>
      <ScrollView
        bounces={false}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        style={styles.screen}
      >
        <Animated.View style={animatedSections[0]}>
          <View style={styles.header}>
            <View style={styles.headerCopy}>
              <AppText style={styles.headerTitle}>{getGreeting()}, {displayName}</AppText>
              <AppText style={styles.headerSubtitle}>
                You looked good yesterday. Let&apos;s keep going.
              </AppText>
            </View>

            <Pressable
              onPress={() => push("/profile")}
              style={({ pressed }) => [styles.avatarShell, pressed ? styles.pressed : null]}
            >
              <LinearGradient
                colors={[featurePalette.lavender, featurePalette.blush]}
                end={{ x: 1, y: 1 }}
                start={{ x: 0, y: 0 }}
                style={styles.avatarGradient}
              >
                <AppText style={styles.avatarLetter}>{avatarInitials}</AppText>
              </LinearGradient>
            </Pressable>
          </View>
        </Animated.View>

        <Animated.View style={animatedSections[1]}>
          <View style={styles.heroWrapper}>
            <View style={[styles.heroCard, { shadowColor: "#C6B1FF" }]}>
              <View style={styles.heroOrbTop} />
              <View style={styles.heroOrbBottom} />

              <View style={[styles.heroIconShell, featureShadows.md]}>
                <Feather color={featurePalette.darkText} name="camera" size={42} />
              </View>

              <AppText style={styles.heroTitle}>
                Show me{"\n"}
                <AppText style={styles.heroItalic}>today&apos;s look</AppText>
              </AppText>
              <AppText style={styles.heroSubtitle}>I&apos;ll remember it for you</AppText>

              <View style={styles.heroActions}>
                <Pressable
                  onPress={() => void handleHeroPhoto()}
                  style={({ pressed }) => [styles.heroPrimaryAction, featureShadows.md, pressed ? styles.pressedWide : null]}
                >
                  <Feather color="#FFFFFF" name="camera" size={20} />
                  <AppText style={styles.heroPrimaryLabel}>Take a Photo</AppText>
                </Pressable>
                <Pressable
                  onPress={() =>
                    router.push(
                      ({ pathname: "/log-outfit", params: { mode: "closet" } } as unknown) as Href
                    )
                  }
                  style={({ pressed }) => [styles.heroSecondaryAction, featureShadows.sm, pressed ? styles.pressedWide : null]}
                >
                  <MaterialCommunityIcons
                    color={featurePalette.darkText}
                    name="hanger"
                    size={20}
                  />
                  <AppText style={styles.heroSecondaryLabel}>Pick from Closet</AppText>
                </Pressable>
              </View>
            </View>
          </View>
        </Animated.View>

        <Animated.View style={animatedSections[2]}>
          <View style={styles.quickStatsRow}>
            {quickStats.map((stat) => (
              <Pressable
                key={stat.label}
                onPress={() => push(stat.route)}
                style={({ pressed }) => [
                  styles.quickStatCard,
                  featureShadows.sm,
                  pressed ? styles.pressedWide : null
                ]}
              >
                <View style={[styles.quickStatIcon, { backgroundColor: stat.background }]}>
                  {stat.icon}
                </View>
                <View style={styles.quickStatCopy}>
                  <AppText style={styles.quickStatValue}>{stat.value}</AppText>
                  <AppText style={styles.quickStatLabel}>{stat.label}</AppText>
                </View>
              </Pressable>
            ))}
          </View>
        </Animated.View>

        <Animated.View style={animatedSections[3]}>
          <View style={styles.section}>
            <AppText style={styles.sectionTitle}>Style Tools</AppText>

            <Pressable
              onPress={() => push("/ai-stylist")}
              style={({ pressed }) => [
                styles.aiStylistCard,
                pressed ? styles.pressedWide : null
              ]}
            >
              <View style={styles.aiStylistCopy}>
                <View style={[styles.toolIconShell, featureShadows.sm]}>
                  <MaterialCommunityIcons color={featurePalette.darkText} name="star-four-points" size={24} />
                </View>
                <AppText style={styles.toolCardTitle}>AI Stylist</AppText>
                <AppText style={styles.toolCardSubtitle}>
                  Get personalized outfit recommendations
                </AppText>
              </View>
              <Image contentFit="cover" source={aiStylistPreview} style={styles.aiStylistImage} />
            </Pressable>

            <View style={styles.toolGrid}>
              <Pressable
                onPress={() => push("/should-i-buy")}
                style={({ pressed }) => [styles.toolSquareCoral, pressed ? styles.pressedWide : null]}
              >
                <View style={[styles.toolIconShell, featureShadows.sm]}>
                  <Feather color={featurePalette.darkText} name="search" size={22} />
                </View>
                <View style={styles.toolSquareCopy}>
                  <AppText style={styles.toolSquareTitle}>Should I Buy</AppText>
                  <AppText style={styles.toolSquareSubtitle}>Match with closet</AppText>
                </View>
              </Pressable>

              <Pressable
                onPress={() => push("/try-on")}
                style={({ pressed }) => [styles.toolSquareSky, pressed ? styles.pressedWide : null]}
              >
                <View style={[styles.toolIconShell, featureShadows.sm]}>
                  <Feather color={featurePalette.darkText} name="camera" size={22} />
                </View>
                <View style={styles.toolSquareCopy}>
                  <AppText style={styles.toolSquareTitle}>Virtual Try-On</AppText>
                  <AppText style={styles.toolSquareSubtitle}>See how it looks</AppText>
                </View>
              </Pressable>
            </View>

            <Pressable
              onPress={() => push("/shop-the-look")}
              style={({ pressed }) => [styles.findItemCard, pressed ? styles.pressedWide : null]}
            >
              <View style={[styles.toolIconShell, featureShadows.sm]}>
                <Feather color={featurePalette.darkText} name="search" size={22} />
              </View>
              <View style={styles.findItemCopy}>
                <AppText style={styles.findItemTitle}>Find This Item</AppText>
                <AppText style={styles.findItemSubtitle}>Scan & identify where to buy</AppText>
              </View>
            </Pressable>
          </View>
        </Animated.View>

        <Animated.View style={animatedSections[4]}>
          <View style={styles.recentLooksSection}>
            <View style={styles.recentLooksHeader}>
              <AppText style={styles.sectionTitle}>Saved Looks</AppText>
              <Pressable onPress={() => push("/lookbook")}>
                <AppText style={styles.seeAllLabel}>See all</AppText>
              </Pressable>
            </View>

            <ScrollView
              contentContainerStyle={styles.recentLooksRow}
              horizontal
              showsHorizontalScrollIndicator={false}
            >
              {recentLooks.map((look) => (
                <Pressable
                  key={look.id}
                  onPress={() => push(`/lookbook/${look.id}`)}
                  style={({ pressed }) => [
                    styles.recentLookCard,
                    { backgroundColor: look.background },
                    featureShadows.md,
                    pressed ? styles.pressedWide : null
                  ]}
                >
                  <View style={styles.recentLookImageFrame}>
                    {look.imageUrl ? (
                      <Image contentFit="cover" source={{ uri: look.imageUrl }} style={styles.recentLookImage} />
                    ) : (
                      <View style={styles.recentLookFallback}>
                        <Feather color={featurePalette.muted} name="image" size={20} />
                      </View>
                    )}
                  </View>
                  <AppText style={styles.recentLookLabel}>{look.label}</AppText>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </Animated.View>
      </ScrollView>

      {showFtue ? (
        <FtueOverlay
          description={homeFtueSteps[ftueStep]?.description ?? ""}
          onDismiss={() => void dismissFtue()}
          onNext={() => void advanceFtue()}
          step={ftueStep}
          title={homeFtueSteps[ftueStep]?.title ?? ""}
          total={homeFtueSteps.length}
        />
      ) : null}
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
    paddingBottom: 132
  },
  header: {
    paddingHorizontal: 24,
    paddingBottom: 8,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12
  },
  headerCopy: {
    flex: 1
  },
  headerTitle: {
    ...featureTypography.displayLarge,
    fontSize: 38,
    lineHeight: 40
  },
  headerSubtitle: {
    ...featureTypography.body,
    marginTop: 6
  },
  avatarShell: {
    width: 52,
    height: 52,
    borderRadius: 26,
    overflow: "hidden",
    borderWidth: 3,
    borderColor: "#FFFFFF"
  },
  avatarGradient: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  avatarLetter: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 18,
    lineHeight: 22,
    color: featurePalette.darkText
  },
  heroWrapper: {
    paddingHorizontal: 24,
    marginTop: 20,
    marginBottom: 28
  },
  heroCard: {
    minHeight: 300,
    borderRadius: 36,
    backgroundColor: featurePalette.lavender,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
    paddingVertical: 28,
    shadowOpacity: 0.25,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 8 },
    elevation: 8
  },
  heroOrbTop: {
    position: "absolute",
    top: -64,
    right: -64,
    width: 192,
    height: 192,
    borderRadius: 96,
    backgroundColor: "rgba(255, 234, 242, 0.5)"
  },
  heroOrbBottom: {
    position: "absolute",
    bottom: -48,
    left: -48,
    width: 144,
    height: 144,
    borderRadius: 72,
    backgroundColor: "rgba(220, 234, 247, 0.5)"
  },
  heroIconShell: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 24
  },
  heroTitle: {
    ...featureTypography.display,
    fontSize: 32,
    lineHeight: 36,
    textAlign: "center",
    marginBottom: 8
  },
  heroItalic: {
    fontFamily: "Newsreader_600SemiBold_Italic",
    fontSize: 32,
    lineHeight: 36,
    color: featurePalette.darkText
  },
  heroSubtitle: {
    ...featureTypography.body,
    textAlign: "center",
    marginBottom: 28
  },
  heroActions: {
    width: "100%",
    gap: 12
  },
  heroPrimaryAction: {
    height: 56,
    borderRadius: 28,
    backgroundColor: featurePalette.darkText,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  heroPrimaryLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 16,
    lineHeight: 20,
    color: "#FFFFFF"
  },
  heroSecondaryAction: {
    height: 56,
    borderRadius: 28,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  heroSecondaryLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 16,
    lineHeight: 20,
    color: featurePalette.darkText
  },
  quickStatsRow: {
    paddingHorizontal: 24,
    marginBottom: 28,
    flexDirection: "row",
    gap: 12
  },
  quickStatCard: {
    flex: 1,
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 12,
    paddingVertical: 16,
    alignItems: "center",
    gap: 10
  },
  quickStatIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center"
  },
  quickStatCopy: {
    alignItems: "center"
  },
  quickStatValue: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 22,
    lineHeight: 24,
    color: featurePalette.darkText
  },
  quickStatLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.warmGray,
    textAlign: "center",
    marginTop: 2
  },
  section: {
    paddingHorizontal: 24,
    marginBottom: 28
  },
  sectionTitle: {
    fontFamily: "Newsreader_500Medium_Italic",
    fontSize: 20,
    lineHeight: 24,
    color: featurePalette.darkText,
    marginBottom: 20
  },
  aiStylistCard: {
    borderRadius: 32,
    backgroundColor: featurePalette.sage,
    paddingHorizontal: 28,
    paddingVertical: 28,
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16
  },
  aiStylistCopy: {
    flex: 1,
    paddingRight: 16
  },
  toolIconShell: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16
  },
  toolCardTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 22,
    lineHeight: 26,
    color: featurePalette.darkText,
    marginBottom: 4
  },
  toolCardSubtitle: {
    ...featureTypography.body,
    fontSize: 14,
    lineHeight: 20
  },
  aiStylistImage: {
    width: 90,
    height: 120,
    borderRadius: 24
  },
  toolGrid: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 16
  },
  toolSquareCoral: {
    flex: 1,
    aspectRatio: 1,
    borderRadius: 28,
    backgroundColor: "#FFD2C2",
    paddingHorizontal: 20,
    paddingVertical: 24,
    justifyContent: "space-between"
  },
  toolSquareSky: {
    flex: 1,
    aspectRatio: 1,
    borderRadius: 28,
    backgroundColor: featurePalette.sky,
    paddingHorizontal: 20,
    paddingVertical: 24,
    justifyContent: "space-between"
  },
  toolSquareCopy: {
    gap: 2
  },
  toolSquareTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 17,
    lineHeight: 21,
    color: featurePalette.darkText
  },
  toolSquareSubtitle: {
    fontFamily: "Manrope_500Medium",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.warmGray
  },
  findItemCard: {
    borderRadius: 28,
    backgroundColor: featurePalette.butter,
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    paddingHorizontal: 24,
    paddingVertical: 20
  },
  findItemCopy: {
    flex: 1
  },
  findItemTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 17,
    lineHeight: 21,
    color: featurePalette.darkText,
    marginBottom: 4
  },
  findItemSubtitle: {
    fontFamily: "Manrope_500Medium",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.warmGray
  },
  recentLooksSection: {
    marginTop: 4
  },
  recentLooksHeader: {
    paddingHorizontal: 24,
    marginBottom: 16,
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between"
  },
  seeAllLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 13,
    lineHeight: 16,
    color: featurePalette.warmGray
  },
  recentLooksRow: {
    paddingLeft: 24,
    paddingRight: 40,
    paddingBottom: 20,
    gap: 14
  },
  recentLookCard: {
    width: 148,
    height: 210,
    borderRadius: 28,
    padding: 14
  },
  recentLookImageFrame: {
    flex: 1,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: "#FFFFFF"
  },
  recentLookImage: {
    width: "100%",
    height: "100%"
  },
  recentLookFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  recentLookLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 11,
    lineHeight: 14,
    textAlign: "center",
    color: featurePalette.darkText,
    marginTop: 10
  },
  pressed: {
    transform: [{ scale: 0.96 }]
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
