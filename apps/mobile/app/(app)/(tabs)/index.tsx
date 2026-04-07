import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { router, type Href } from "expo-router";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Animated,
  Easing,
  Modal,
  Pressable,
  StyleSheet,
  View,
  type ImageSourcePropType
} from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useClosetInsights } from "../../../src/closet/insights";
import { useInsightOverview } from "../../../src/home/overview";
import { aiStylistPreview, homeRecentLooks } from "../../../src/home/reference";
import { hasSeenHomeFtue, markHomeFtueSeen } from "../../../src/home/storage";
import { useProfile } from "../../../src/profile/hooks";
import { colors, fontFamilies } from "../../../src/theme";
import { AppText, Screen } from "../../../src/ui";

const palette = {
  cream: colors.cream,
  warmWhite: colors.warmWhite,
  darkText: colors.darkText,
  warmGray: "#64748B",
  coral: "#FF6B6B",
  coralSoft: "#FF8A80",
  coralSurface: "#FFF1F1",
  sage: colors.sage,
  lavender: colors.lavender,
  butter: colors.butter,
  sky: colors.sky,
  blush: colors.blush,
  mint: colors.mint,
  overlay: "rgba(15, 23, 42, 0.4)"
} as const;

const ftueSteps = [
  {
    title: "Add your first item",
    description: "Snap a photo of something you wear. We'll handle the review flow from there.",
    icon: "tshirt-crew-outline" as const
  },
  {
    title: "Log your first outfit",
    description: "The styling and lookbook flows come next. This home screen is ready for them.",
    icon: "camera-outline" as const
  }
];

type StatCardData = {
  label: string;
  route: Href;
  value: string;
  tint: string;
  iconColor: string;
  icon: "closet" | "camera" | "flame";
};

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

function getStatIcon(icon: StatCardData["icon"], color: string) {
  if (icon === "closet") {
    return <MaterialCommunityIcons color={color} name="hanger" size={18} />;
  }

  if (icon === "camera") {
    return <Feather color={color} name="camera" size={17} />;
  }

  return <MaterialCommunityIcons color={color} name="fire" size={18} />;
}

export default function HomeScreen() {
  const { logoutCurrentUser, session, user } = useAuth();
  const profile = useProfile({
    accessToken: session?.access_token,
    onUnauthorized: async () => {
      await logoutCurrentUser();
      router.replace("/login");
    }
  });
  const closetInsights = useClosetInsights(session?.access_token);
  const insightOverview = useInsightOverview(session?.access_token);

  const [showFtue, setShowFtue] = useState(false);
  const [ftueStepIndex, setFtueStepIndex] = useState(0);
  const animations = useRef(
    Array.from({ length: 5 }, () => new Animated.Value(0))
  ).current;

  useEffect(() => {
    Animated.stagger(
      60,
      animations.map((value) =>
        Animated.timing(value, {
          toValue: 1,
          duration: 360,
          easing: Easing.bezier(0.32, 0.72, 0, 1),
          useNativeDriver: true
        })
      )
    ).start();
  }, [animations]);

  useEffect(() => {
    let active = true;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    async function maybeShowFtue() {
      const seen = await hasSeenHomeFtue();
      if (!active || seen) {
        return;
      }

      timeoutId = setTimeout(() => {
        if (active) {
          setShowFtue(true);
        }
      }, 800);
    }

    void maybeShowFtue();

    return () => {
      active = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, []);

  const displayName = buildDisplayName(profile.profile?.display_name, user?.email);
  const avatarInitials = getInitials(displayName);
  const closetCount = closetInsights.insights.totalItems;
  const streakCount = insightOverview.data?.streaks.current_streak_days ?? 0;

  const stats = useMemo<StatCardData[]>(
    () => [
      {
        label: "Closet items",
        route: "/closet",
        value: `${closetCount}`,
        tint: "rgba(216, 235, 207, 0.72)",
        iconColor: "#567848",
        icon: "closet"
      },
      {
        label: "Saved outfits",
        route: "/style",
        value: `${homeRecentLooks.length}`,
        tint: "rgba(232, 219, 255, 0.82)",
        iconColor: "#7658C3",
        icon: "camera"
      },
      {
        label: "Day streak",
        route: "/insights",
        value: `${streakCount}`,
        tint: "rgba(255, 210, 194, 0.82)",
        iconColor: "#E46B34",
        icon: "flame"
      }
    ],
    [closetCount, streakCount]
  );

  async function dismissFtue() {
    setShowFtue(false);
    setFtueStepIndex(0);
    await markHomeFtueSeen();
  }

  async function advanceFtue() {
    if (ftueStepIndex < ftueSteps.length - 1) {
      setFtueStepIndex((current) => current + 1);
      return;
    }

    await dismissFtue();
  }

  return (
    <>
      <Screen
        backgroundColor={palette.cream}
        contentContainerStyle={styles.screenContent}
        padded={false}
      >
        <Animated.View style={[styles.section, buildAnimatedStyle(animations[0])]}>
          <View style={styles.header}>
            <View style={styles.headerCopy}>
              <AppText
                adjustsFontSizeToFit
                minimumFontScale={0.82}
                numberOfLines={1}
                style={styles.headerTitle}
              >
                {getGreeting()}, {displayName}
              </AppText>
              <AppText color={palette.warmGray} style={styles.headerSubtitle}>
                You looked good yesterday. Let&apos;s keep going.
              </AppText>
            </View>

            <Pressable
              onPress={() => router.push("/profile" as Href)}
              style={({ pressed }) => [styles.avatarShell, pressed ? styles.pressed : null]}
            >
              <LinearGradient
                colors={["#E8DBFF", "#FFEAF2"]}
                end={{ x: 1, y: 1 }}
                start={{ x: 0, y: 0 }}
                style={styles.avatarGradient}
              >
                <AppText style={styles.avatarText}>{avatarInitials}</AppText>
              </LinearGradient>
            </Pressable>
          </View>
        </Animated.View>

        <Animated.View style={[styles.section, buildAnimatedStyle(animations[1])]}>
          <View style={styles.heroWrapper}>
            <View style={styles.heroCard}>
              <LinearGradient
                colors={["rgba(220, 234, 247, 0.52)", "rgba(220, 234, 247, 0.16)", "rgba(220, 234, 247, 0)"]}
                end={{ x: 0.85, y: 0.85 }}
                start={{ x: 0.2, y: 0.2 }}
                style={styles.heroOrbBottom}
              />

              <View style={styles.heroIconCircle}>
                <Feather color={palette.darkText} name="camera" size={42} strokeWidth={1.8} />
              </View>

              <View style={styles.heroCopy}>
                <AppText style={styles.heroTitle}>Show me</AppText>
                <AppText style={styles.heroTitleItalic}>today&apos;s look</AppText>
                <AppText color={palette.warmGray} style={styles.heroSubtitle}>
                  I&apos;ll remember it for you
                </AppText>
              </View>

              <View style={styles.heroActions}>
                <Pressable
                  onPress={() => router.push("/add" as Href)}
                  style={({ pressed }) => [styles.heroPrimaryButton, pressed ? styles.pressed : null]}
                >
                  <Feather color={palette.warmWhite} name="camera" size={18} strokeWidth={2.5} />
                  <AppText color={palette.warmWhite} style={styles.heroPrimaryLabel}>
                    Take a Photo
                  </AppText>
                </Pressable>

                <Pressable
                  onPress={() => router.push("/closet" as Href)}
                  style={({ pressed }) => [styles.heroSecondaryButton, pressed ? styles.pressed : null]}
                >
                  <MaterialCommunityIcons color={palette.darkText} name="tshirt-crew-outline" size={20} />
                  <AppText color={palette.darkText} style={styles.heroSecondaryLabel}>
                    Pick from Closet
                  </AppText>
                </Pressable>
              </View>
            </View>
          </View>
        </Animated.View>

        <Animated.View style={[styles.section, buildAnimatedStyle(animations[2])]}>
          <View style={styles.statsRow}>
            {stats.map((stat) => (
              <Pressable
                key={stat.label}
                onPress={() => router.push(stat.route)}
                style={({ pressed }) => [styles.statCard, pressed ? styles.pressed : null]}
              >
                <View style={[styles.statIconCircle, { backgroundColor: stat.tint }]}>
                  {getStatIcon(stat.icon, stat.iconColor)}
                </View>
                <View style={styles.statCopy}>
                  <AppText style={styles.statValue}>{stat.value}</AppText>
                  <AppText color={palette.warmGray} style={styles.statLabel}>
                    {stat.label}
                  </AppText>
                </View>
              </Pressable>
            ))}
          </View>
        </Animated.View>

        <Animated.View style={[styles.section, buildAnimatedStyle(animations[3])]}>
          <View style={styles.toolsSection}>
            <AppText style={styles.sectionTitle}>Style Tools</AppText>

            <Pressable
              onPress={() => router.push("/style" as Href)}
              style={({ pressed }) => [styles.aiCard, pressed ? styles.pressed : null]}
            >
              <View style={styles.aiCardCopy}>
                <View style={styles.aiIconCircle}>
                  <MaterialCommunityIcons
                    color={palette.darkText}
                    name="auto-fix"
                    size={24}
                  />
                </View>
                <AppText style={styles.aiCardTitle}>AI Stylist</AppText>
                <AppText color={palette.warmGray} style={styles.aiCardSubtitle}>
                  Get personalized outfit recommendations
                </AppText>
              </View>

              <Image
                contentFit="cover"
                source={aiStylistPreview as ImageSourcePropType}
                style={styles.aiPreview}
              />
            </Pressable>

            <View style={styles.toolsGrid}>
              <ToolCard
                backgroundColor="#FFD2C2"
                icon={<Feather color={palette.darkText} name="search" size={22} />}
                subtitle="Match with closet"
                title="Should I Buy"
                onPress={() => router.push("/style" as Href)}
              />
              <ToolCard
                backgroundColor="#DCEAF7"
                icon={<Feather color={palette.darkText} name="camera" size={22} />}
                subtitle="See how it looks"
                title="Virtual Try-On"
                onPress={() => router.push("/style" as Href)}
              />
            </View>

            <Pressable
              onPress={() => router.push("/style" as Href)}
              style={({ pressed }) => [styles.findCard, pressed ? styles.pressed : null]}
            >
              <View style={styles.findIconCircle}>
                <MaterialCommunityIcons color={palette.darkText} name="line-scan" size={22} />
              </View>
              <View style={styles.findCopy}>
                <AppText style={styles.findTitle}>Find This Item</AppText>
                <AppText color={palette.warmGray} style={styles.findSubtitle}>
                  Scan and identify where to buy
                </AppText>
              </View>
            </Pressable>
          </View>
        </Animated.View>

        <Animated.View style={[styles.section, buildAnimatedStyle(animations[4])]}>
          <View style={styles.recentSection}>
            <View style={styles.sectionHeader}>
              <AppText style={styles.sectionTitle}>Saved Looks</AppText>
              <Pressable onPress={() => router.push("/style" as Href)}>
                <AppText color={palette.warmGray} style={styles.seeAllLabel}>
                  See all
                </AppText>
              </Pressable>
            </View>

            <View style={styles.recentScrollMask}>
              <Animated.ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.recentRow}
              >
                {homeRecentLooks.map((look) => (
                  <Pressable
                    key={look.id}
                    onPress={() => router.push("/style" as Href)}
                    style={({ pressed }) => [styles.lookCard, { backgroundColor: look.tint }, pressed ? styles.pressed : null]}
                  >
                    <View style={styles.lookImageFrame}>
                      <Image
                        contentFit="cover"
                        source={look.image as ImageSourcePropType}
                        style={styles.lookImage}
                      />
                    </View>
                    <AppText style={styles.lookLabel}>{look.label}</AppText>
                  </Pressable>
                ))}
              </Animated.ScrollView>
            </View>
          </View>
        </Animated.View>
      </Screen>

      <Modal animationType="fade" transparent visible={showFtue}>
        <View style={styles.ftueBackdrop}>
          <Pressable onPress={() => void dismissFtue()} style={StyleSheet.absoluteFillObject} />
          <View style={styles.ftueCard}>
            <Pressable
              onPress={() => void dismissFtue()}
              style={({ pressed }) => [styles.ftueClose, pressed ? styles.pressed : null]}
            >
              <Feather color="#94A3B8" name="x" size={16} />
            </Pressable>

            <View style={styles.ftueIconCircle}>
              {ftueSteps[ftueStepIndex].icon === "tshirt-crew-outline" ? (
                <MaterialCommunityIcons color={palette.coral} name="tshirt-crew-outline" size={26} />
              ) : (
                <Feather color={palette.coral} name="camera" size={24} />
              )}
            </View>

            <AppText style={styles.ftueTitle}>{ftueSteps[ftueStepIndex].title}</AppText>
            <AppText color="#64748B" style={styles.ftueDescription}>
              {ftueSteps[ftueStepIndex].description}
            </AppText>

            <View style={styles.ftueFooter}>
              <View style={styles.ftueDots}>
                {ftueSteps.map((step, index) => (
                  <View
                    key={step.title}
                    style={[
                      styles.ftueDot,
                      index === ftueStepIndex ? styles.ftueDotActive : null
                    ]}
                  />
                ))}
              </View>

              <Pressable
                onPress={() => void advanceFtue()}
                style={({ pressed }) => [styles.ftuePrimaryAction, pressed ? styles.pressed : null]}
              >
                <LinearGradient
                  colors={[palette.coral, palette.coralSoft]}
                  end={{ x: 1, y: 1 }}
                  start={{ x: 0, y: 0 }}
                  style={styles.ftuePrimaryGradient}
                >
                  <AppText color={palette.warmWhite} style={styles.ftuePrimaryLabel}>
                    {ftueStepIndex < ftueSteps.length - 1 ? "Next" : "Got it"}
                  </AppText>
                </LinearGradient>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

function ToolCard({
  backgroundColor,
  icon,
  subtitle,
  title,
  onPress
}: {
  backgroundColor: string;
  icon: ReactNode;
  subtitle: string;
  title: string;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.toolCard, { backgroundColor }, pressed ? styles.pressed : null]}>
      <View style={styles.toolIconCircle}>{icon}</View>
      <View style={styles.toolCopy}>
        <AppText style={styles.toolTitle}>{title}</AppText>
        <AppText color={palette.warmGray} style={styles.toolSubtitle}>
          {subtitle}
        </AppText>
      </View>
    </Pressable>
  );
}

function buildAnimatedStyle(value: Animated.Value) {
  return {
    opacity: value,
    transform: [
      {
        translateY: value.interpolate({
          inputRange: [0, 1],
          outputRange: [14, 0]
        })
      }
    ]
  };
}

const styles = StyleSheet.create({
  screenContent: {
    paddingBottom: 24
  },
  section: {
    paddingHorizontal: 24
  },
  header: {
    paddingTop: 28,
    paddingBottom: 4,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16
  },
  headerCopy: {
    flex: 1,
    gap: 4
  },
  headerTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 38,
    lineHeight: 42,
    letterSpacing: -0.76,
    color: palette.darkText
  },
  headerSubtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 22
  },
  avatarShell: {
    width: 52,
    height: 52,
    borderRadius: 26,
    padding: 3,
    backgroundColor: palette.warmWhite,
    shadowColor: "#B8A7DE",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 16,
    elevation: 7
  },
  avatarGradient: {
    flex: 1,
    borderRadius: 23,
    alignItems: "center",
    justifyContent: "center"
  },
  avatarText: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 18,
    lineHeight: 20,
    color: palette.darkText
  },
  heroWrapper: {
    marginTop: 20,
    marginBottom: 32
  },
  heroCard: {
    minHeight: 320,
    borderRadius: 36,
    paddingHorizontal: 26,
    paddingVertical: 30,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.lavender,
    overflow: "hidden",
    shadowColor: "#C8B2E8",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.32,
    shadowRadius: 24,
    elevation: 10
  },
  heroOrbBottom: {
    position: "absolute",
    bottom: -54,
    left: -36,
    width: 176,
    height: 176,
    borderRadius: 88,
    opacity: 0.8
  },
  heroIconCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.warmWhite,
    marginBottom: 24,
    shadowColor: "#171411",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.1,
    shadowRadius: 16,
    elevation: 5
  },
  heroCopy: {
    alignItems: "center",
    gap: 6,
    marginBottom: 30
  },
  heroTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 42,
    lineHeight: 44,
    letterSpacing: -1,
    color: palette.darkText,
    textAlign: "center"
  },
  heroTitleItalic: {
    fontFamily: fontFamilies.serifSemiBoldItalic,
    fontSize: 30,
    lineHeight: 32,
    letterSpacing: -0.6,
    color: palette.darkText,
    textAlign: "center"
  },
  heroSubtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 16,
    lineHeight: 22,
    textAlign: "center",
    marginTop: 12
  },
  heroActions: {
    alignSelf: "stretch",
    gap: 12
  },
  heroPrimaryButton: {
    height: 58,
    borderRadius: 28,
    backgroundColor: palette.darkText,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 14,
    elevation: 6
  },
  heroPrimaryLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 17,
    lineHeight: 21
  },
  heroSecondaryButton: {
    height: 58,
    borderRadius: 28,
    backgroundColor: palette.warmWhite,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    shadowColor: "#171411",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3
  },
  heroSecondaryLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 17,
    lineHeight: 21
  },
  statsRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 32
  },
  statCard: {
    flex: 1,
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 10,
    paddingVertical: 16,
    borderRadius: 24,
    backgroundColor: palette.warmWhite,
    shadowColor: "#171411",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3
  },
  statIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center"
  },
  statCopy: {
    alignItems: "center",
    gap: 2
  },
  statValue: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 22,
    lineHeight: 24,
    color: palette.darkText
  },
  statLabel: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 11,
    lineHeight: 14,
    textAlign: "center"
  },
  toolsSection: {
    marginBottom: 32
  },
  sectionTitle: {
    fontFamily: fontFamilies.serifMediumItalic,
    fontSize: 20,
    lineHeight: 24,
    color: palette.darkText,
    letterSpacing: -0.4,
    marginBottom: 20
  },
  aiCard: {
    borderRadius: 32,
    backgroundColor: palette.sage,
    padding: 24,
    marginBottom: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    shadowColor: "#7A8F69",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.18,
    shadowRadius: 16,
    elevation: 5
  },
  aiCardCopy: {
    flex: 1,
    gap: 8
  },
  aiIconCircle: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.warmWhite,
    shadowColor: "#171411",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3
  },
  aiCardTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 22,
    lineHeight: 26,
    color: palette.darkText
  },
  aiCardSubtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 20
  },
  aiPreview: {
    width: 90,
    height: 120,
    borderRadius: 24
  },
  toolsGrid: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 16
  },
  toolCard: {
    flex: 1,
    aspectRatio: 1,
    borderRadius: 28,
    padding: 24,
    justifyContent: "space-between",
    shadowColor: "#171411",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4
  },
  toolIconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.warmWhite,
    shadowColor: "#171411",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 2
  },
  toolCopy: {
    gap: 4
  },
  toolTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 17,
    lineHeight: 21,
    color: palette.darkText
  },
  toolSubtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16
  },
  findCard: {
    borderRadius: 28,
    backgroundColor: palette.butter,
    paddingHorizontal: 24,
    paddingVertical: 20,
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    shadowColor: "#B39F35",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.14,
    shadowRadius: 12,
    elevation: 4
  },
  findIconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.warmWhite,
    shadowColor: "#171411",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 2
  },
  findCopy: {
    flex: 1,
    gap: 4
  },
  findTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 17,
    lineHeight: 20,
    color: palette.darkText
  },
  findSubtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
  },
  recentSection: {
    marginBottom: 24
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    marginBottom: 16
  },
  seeAllLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18
  },
  recentScrollMask: {
    marginHorizontal: -24
  },
  recentRow: {
    paddingLeft: 24,
    paddingRight: 40,
    paddingBottom: 4,
    gap: 14
  },
  lookCard: {
    width: 148,
    height: 210,
    borderRadius: 28,
    padding: 14,
    justifyContent: "space-between",
    shadowColor: "#171411",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 14,
    elevation: 4
  },
  lookImageFrame: {
    flex: 1,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: palette.warmWhite
  },
  lookImage: {
    width: "100%",
    height: "100%"
  },
  lookLabel: {
    marginTop: 10,
    textAlign: "center",
    fontFamily: fontFamilies.sansBold,
    fontSize: 11,
    lineHeight: 14,
    color: palette.darkText
  },
  ftueBackdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: palette.overlay,
    paddingHorizontal: 16,
    paddingBottom: 32
  },
  ftueCard: {
    borderRadius: 24,
    padding: 24,
    backgroundColor: palette.warmWhite,
    shadowColor: "#171411",
    shadowOffset: { width: 0, height: 20 },
    shadowOpacity: 0.15,
    shadowRadius: 28,
    elevation: 12
  },
  ftueClose: {
    position: "absolute",
    top: 16,
    right: 16,
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F8F8F6",
    zIndex: 1
  },
  ftueIconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.coralSurface,
    marginBottom: 16
  },
  ftueTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 20,
    lineHeight: 24,
    letterSpacing: -0.4,
    color: palette.darkText,
    marginBottom: 6
  },
  ftueDescription: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 22,
    marginBottom: 24
  },
  ftueFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16
  },
  ftueDots: {
    flexDirection: "row",
    gap: 6,
    alignItems: "center"
  },
  ftueDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#E8E8E6"
  },
  ftueDotActive: {
    width: 20,
    backgroundColor: palette.coral
  },
  ftuePrimaryAction: {
    borderRadius: 22,
    overflow: "hidden"
  },
  ftuePrimaryGradient: {
    minWidth: 112,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24
  },
  ftuePrimaryLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 14,
    lineHeight: 18
  },
  pressed: {
    transform: [{ scale: 0.98 }]
  }
});
