import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { router, type Href } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useReviewQueue } from "../../../src/closet/hooks";
import { useClosetInsights } from "../../../src/closet/insights";
import { useInsightOverview } from "../../../src/home/overview";
import { humanizeEnum } from "../../../src/lib/format";
import { triggerSuccessHaptic } from "../../../src/lib/haptics";
import { LOOKBOOK_ENTRIES } from "../../../src/lib/reference/wardrobe";
import { useProfile } from "../../../src/profile/hooks";
import {
  buildProfileCompletion,
  buildProfileDescriptor,
  buildProfileDisplayName,
  buildProfileInitials,
  buildProfileSavedEntries
} from "../../../src/profile/selectors";
import { colors, radius, spacing } from "../../../src/theme";
import { featurePalette, featureShadows, featureTypography } from "../../../src/theme/feature";
import {
  AppText,
  BrandMark,
  Button,
  Card,
  Chip,
  Screen,
  TextField
} from "../../../src/ui";
import { GlassIconButton } from "../../../src/ui/feature-components";
import { formatLocalDate } from "../../../src/wear/dates";
import { useWearCalendar, useWearTimeline } from "../../../src/wear/hooks";

type ProfileSectionKey = "looks" | "calendar" | "saved" | "signals";

const PROFILE_SECTIONS: Array<{ key: ProfileSectionKey; label: string }> = [
  { key: "looks", label: "Looks" },
  { key: "calendar", label: "Calendar" },
  { key: "saved", label: "Saved" },
  { key: "signals", label: "Signals" }
];

function normalizeOptionalField(value: string): string | null {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

export default function ProfileScreen() {
  const { logoutCurrentUser, session, user } = useAuth();
  const profile = useProfile({
    accessToken: session?.access_token,
    onUnauthorized: async () => {
      await logoutCurrentUser();
      router.replace("/login");
    }
  });
  const reviewQueue = useReviewQueue(session?.access_token);
  const insights = useClosetInsights(session?.access_token);
  const overview = useInsightOverview(session?.access_token);
  const wearTimeline = useWearTimeline(session?.access_token, {}, 5);
  const wearCalendar = useWearCalendar(session?.access_token, 14);

  const [selectedSection, setSelectedSection] = useState<ProfileSectionKey>("looks");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    setUsername(profile.profile?.username ?? "");
    setDisplayName(profile.profile?.display_name ?? "");
    setBio(profile.profile?.bio ?? "");
  }, [profile.profile]);

  const savedEntries = useMemo(
    () => buildProfileSavedEntries(
      LOOKBOOK_ENTRIES.filter((entry) => entry.type === "inspiration").length
        ? LOOKBOOK_ENTRIES.filter((entry) => entry.type === "inspiration")
        : LOOKBOOK_ENTRIES,
      4
    ),
    []
  );
  const todayKey = formatLocalDate(new Date());
  const recentLooks = useMemo(
    () =>
      wearTimeline.items.slice(0, 5).map((item) => ({
        dateKey: item.wear_date,
        id: item.id,
        image: item.cover_image?.url ? ({ uri: item.cover_image.url } as const) : null,
        itemCount: item.item_count,
        note: item.is_confirmed ? "Saved to your wear history." : `${humanizeEnum(item.status)} and waiting for review.`,
        subtitle: new Intl.DateTimeFormat(undefined, {
          month: "short",
          day: "numeric"
        }).format(new Date(`${item.wear_date}T12:00:00`)),
        title: item.outfit_title ?? (item.context ? humanizeEnum(item.context) : "Wear log")
      })),
    [wearTimeline.items]
  );
  const calendarDays = useMemo(
    () =>
      wearCalendar.days.map((day) => {
        const date = new Date(`${day.date}T12:00:00`);
        return {
          dateKey: day.date,
          dayLabel: date.toLocaleDateString(undefined, { weekday: "short" }).slice(0, 3),
          dayNumber: `${date.getDate()}`,
          hasOutfit: day.has_wear_log,
          isToday: day.date === todayKey,
          wearLogId: day.primary_event_id
        };
      }),
    [todayKey, wearCalendar.days]
  );
  const streak = overview.data?.streaks.current_streak_days ?? 0;

  const displayTitle = buildProfileDisplayName(profile.profile, user?.email);
  const initials = buildProfileInitials(displayTitle);
  const descriptor = buildProfileDescriptor(profile.profile, insights.insights);
  const completion = buildProfileCompletion(profile.profile);
  const todayLook = wearCalendar.days.find((day) => day.date === todayKey) ?? null;
  const todayLookExists = Boolean(todayLook?.primary_event_id);
  const todayWearLogId = todayLook?.primary_event_id ?? null;

  const needsReviewCount =
    reviewQueue.sections.find((section) => section.key === "needs_review")?.items.length ?? 0;
  const processedCoverage =
    insights.insights.totalItems === 0
      ? "0%"
      : `${Math.round((insights.insights.processedItems / insights.insights.totalItems) * 100)}%`;

  async function handleSave() {
    const nextProfile = await profile.saveProfile({
      username: normalizeOptionalField(username),
      display_name: normalizeOptionalField(displayName),
      bio: normalizeOptionalField(bio)
    });

    if (!nextProfile) {
      return;
    }

    await triggerSuccessHaptic();
    setNotice("Profile saved.");
  }

  async function handleLogout() {
    await logoutCurrentUser();
    router.replace("/login");
  }

  function push(href: string) {
    router.push(href as Href);
  }

  return (
    <Screen backgroundColor={featurePalette.background} contentContainerStyle={styles.content}>
      <View style={styles.topRow}>
        <BrandMark variant="wordmark" subtle />
        <View style={styles.topActions}>
          <GlassIconButton
            icon={<Feather color={featurePalette.foreground} name="settings" size={17} />}
            onPress={() => push("/settings")}
          />
          <Pressable
            onPress={() => void handleLogout()}
            style={({ pressed }) => [
              styles.signOutPill,
              pressed ? styles.pressedWide : null
            ]}
          >
            <AppText style={styles.signOutLabel}>Sign out</AppText>
          </Pressable>
        </View>
      </View>

      <LinearGradient
        colors={["#F7EFE6", "#F8F4FF", "#FFFFFF"]}
        end={{ x: 1, y: 1 }}
        start={{ x: 0, y: 0 }}
        style={[styles.heroCard, featureShadows.lg]}
      >
        <View style={styles.heroGlowTop} />
        <View style={styles.heroGlowBottom} />

        <View style={styles.heroBadgeRow}>
          <Chip label={`${completion}% profile`} tone="lookbook" />
          <Chip label="Private wardrobe identity" tone="organize" />
        </View>

        <View style={styles.heroRow}>
          <LinearGradient
            colors={[featurePalette.lavender, featurePalette.blush]}
            end={{ x: 1, y: 1 }}
            start={{ x: 0, y: 0 }}
            style={styles.avatarShell}
          >
            <AppText style={styles.avatarLabel}>{initials}</AppText>
          </LinearGradient>

          <View style={styles.heroCopy}>
            <AppText style={styles.heroTitle}>{displayTitle}</AppText>
            <AppText style={styles.heroHandle}>
              {profile.profile?.username ? `@${profile.profile.username}` : "Claim your username"}
            </AppText>
            <AppText style={styles.heroDescriptor}>{descriptor}</AppText>
          </View>
        </View>

        <View style={styles.heroStatsRow}>
          <HeroMetric
            icon={<MaterialCommunityIcons color="#4C6B40" name="hanger" size={16} />}
            label="Closet"
            tone="sage"
            value={`${insights.insights.totalItems}`}
          />
          <HeroMetric
            icon={<Feather color="#8F5FCB" name="camera" size={15} />}
            label="Looks"
            tone="lavender"
            value={`${overview.data?.all_time.total_wear_logs ?? recentLooks.length}`}
          />
          <HeroMetric
            icon={<MaterialCommunityIcons color="#DE6D39" name="fire" size={16} />}
            label="Streak"
            tone="blush"
            value={`${streak}`}
          />
        </View>

        <View style={styles.heroActionRow}>
          <Pressable
            onPress={() => push(todayWearLogId ? `/wear/${todayWearLogId}` : "/log-outfit")}
            style={({ pressed }) => [
              styles.heroPrimaryAction,
              featureShadows.md,
              pressed ? styles.pressedWide : null
            ]}
          >
            <Feather color="#FFFFFF" name="camera" size={18} />
            <AppText style={styles.heroPrimaryActionLabel}>
              {todayLookExists ? "Open Today&apos;s Look" : "Log Today&apos;s Look"}
            </AppText>
          </Pressable>

          <Pressable
            onPress={() => push("/stats")}
            style={({ pressed }) => [
              styles.heroSecondaryAction,
              featureShadows.sm,
              pressed ? styles.pressedWide : null
            ]}
          >
            <Feather color={featurePalette.foreground} name="bar-chart-2" size={18} />
            <AppText style={styles.heroSecondaryActionLabel}>Signals</AppText>
          </Pressable>
        </View>
      </LinearGradient>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.segmentRow}
      >
        {PROFILE_SECTIONS.map((segment) => {
          const active = selectedSection === segment.key;
          return (
            <Pressable
              key={segment.key}
              onPress={() => setSelectedSection(segment.key)}
              style={[
                styles.segment,
                active ? styles.segmentActive : null,
                featureShadows.sm
              ]}
            >
              <AppText style={[styles.segmentLabel, active ? styles.segmentLabelActive : null]}>
                {segment.label}
              </AppText>
            </Pressable>
          );
        })}
      </ScrollView>

      {selectedSection === "looks" ? (
        <View style={styles.section}>
          <SectionHeader
            actionLabel="Open history"
            onPress={() => push("/wear")}
            title="Recent Looks"
          />

          {recentLooks.length ? (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.looksRow}
            >
              {recentLooks.map((look) => (
                <Pressable
                  key={look.id}
                  onPress={() => push(`/wear/${look.id}`)}
                  style={({ pressed }) => [
                    styles.lookCard,
                    featureShadows.md,
                    pressed ? styles.pressedWide : null
                  ]}
                >
                  <View style={styles.lookImageFrame}>
                    {look.image ? (
                      <Image contentFit="cover" source={look.image} style={styles.lookImage} />
                    ) : (
                      <View style={styles.lookImagePlaceholder}>
                        <Feather color={featurePalette.muted} name="camera" size={22} />
                      </View>
                    )}
                  </View>
                  <View style={styles.lookCardCopy}>
                    <AppText style={styles.lookCardTitle}>{look.title}</AppText>
                    <AppText style={styles.lookCardMeta}>
                      {look.subtitle} · {look.itemCount} items
                    </AppText>
                    <AppText numberOfLines={2} style={styles.lookCardNote}>
                      {look.note ?? "Saved to your outfit history."}
                    </AppText>
                  </View>
                </Pressable>
              ))}
            </ScrollView>
          ) : (
            <EmptyProfileCard
              actionLabel="Log your first look"
              copy={wearTimeline.error ?? "Outfit history will start building here as soon as you log what you wore."}
              icon="camera"
              onPress={() => push("/log-outfit")}
              title="Nothing logged yet"
            />
          )}
        </View>
      ) : null}

      {selectedSection === "calendar" ? (
        <View style={styles.section}>
          <SectionHeader
            actionLabel="Open today"
            onPress={() => push(todayWearLogId ? `/wear/${todayWearLogId}` : "/log-outfit")}
            title="Wear Calendar"
          />

          <View style={[styles.calendarCard, featureShadows.sm]}>
            <View style={styles.calendarHeader}>
              <View>
                <AppText style={styles.calendarTitle}>Last 14 days</AppText>
                <AppText style={styles.calendarSubtitle}>
                  Tap a day to open the look or log it.
                </AppText>
              </View>
              <View style={styles.calendarStreakPill}>
                <MaterialCommunityIcons color="#DE6D39" name="fire" size={16} />
                <AppText style={styles.calendarStreakLabel}>{streak} day streak</AppText>
              </View>
            </View>

            <View style={styles.calendarGrid}>
              {calendarDays.map((day) => (
                <Pressable
                  key={day.dateKey}
                  onPress={() => push(day.wearLogId ? `/wear/${day.wearLogId}` : "/log-outfit")}
                  style={[
                    styles.calendarDay,
                    day.hasOutfit ? styles.calendarDayFilled : null,
                    day.isToday ? styles.calendarDayToday : null
                  ]}
                >
                  <AppText style={[styles.calendarDayLabel, day.hasOutfit ? styles.calendarDayLabelFilled : null]}>
                    {day.dayLabel}
                  </AppText>
                  <AppText style={[styles.calendarDayNumber, day.hasOutfit ? styles.calendarDayLabelFilled : null]}>
                    {day.dayNumber}
                  </AppText>
                </Pressable>
              ))}
            </View>
          </View>
        </View>
      ) : null}

      {selectedSection === "saved" ? (
        <View style={styles.section}>
          <SectionHeader
            actionLabel="All saved"
            onPress={() => push("/lookbook")}
            title="Saved Inspiration"
          />

          {savedEntries.length ? (
            <View style={styles.savedGrid}>
              {savedEntries.map((entry) => (
                <Pressable
                  key={entry.id}
                  onPress={() => push(entry.route)}
                  style={({ pressed }) => [
                    styles.savedCard,
                    pressed ? styles.pressedWide : null
                  ]}
                >
                  <View style={styles.savedImageFrame}>
                    <Image contentFit="cover" source={entry.image} style={styles.savedImage} />
                    {entry.type === "inspiration" ? (
                      <View style={styles.savedBadge}>
                        <MaterialCommunityIcons color={featurePalette.foreground} name="star-four-points" size={12} />
                      </View>
                    ) : null}
                  </View>
                  <AppText numberOfLines={1} style={styles.savedTitle}>
                    {entry.title}
                  </AppText>
                  <AppText style={styles.savedMeta}>{entry.meta}</AppText>
                </Pressable>
              ))}
            </View>
          ) : (
            <EmptyProfileCard
              actionLabel="Open lookbook"
              copy="Inspiration and favorite styling outcomes will surface here."
              icon="bookmark"
              onPress={() => push("/lookbook")}
              title="No saved entries yet"
            />
          )}
        </View>
      ) : null}

      {selectedSection === "signals" ? (
        <View style={styles.section}>
          <SectionHeader
            actionLabel="Full dashboard"
            onPress={() => push("/stats")}
            title="Wardrobe Signals"
          />

          <View style={styles.signalGrid}>
            <SignalCard
              icon={<MaterialCommunityIcons color="#4C6B40" name="hanger" size={18} />}
              label="Closet items"
              tone="sage"
              value={`${insights.insights.totalItems}`}
            />
            <SignalCard
              icon={<MaterialCommunityIcons color="#DE6D39" name="progress-check" size={18} />}
              label="Processed"
              tone="blush"
              value={processedCoverage}
            />
            <SignalCard
              icon={<Feather color="#8F5FCB" name="layers" size={18} />}
              label="Top category"
              tone="lavender"
              value={insights.insights.topCategory?.label ?? "Waiting"}
            />
            <SignalCard
              icon={<Feather color="#577B9A" name="droplet" size={18} />}
              label="Top color"
              tone="sky"
              value={insights.insights.topColor?.label ?? "Building"}
            />
          </View>

          <Card tone="organize">
            <AppText color={colors.textSubtle} variant="eyebrow">
              Review pressure
            </AppText>
            <AppText variant="sectionTitle">
              {needsReviewCount > 0
                ? `${needsReviewCount} item${needsReviewCount === 1 ? "" : "s"} still need review.`
                : "The review queue is under control."}
            </AppText>
            <AppText color={colors.textMuted}>
              Keep the closet trustworthy by confirming categories and subcategories before items
              become canonical wardrobe truth.
            </AppText>
          </Card>
        </View>
      ) : null}

      <Card tone="soft" style={styles.formCard}>
        <View style={styles.formHeader}>
          <View>
            <AppText color={colors.textSubtle} variant="eyebrow">
              Edit Profile
            </AppText>
            <AppText variant="sectionTitle">Refine your identity shell.</AppText>
          </View>
          <Pressable
            onPress={() => push("/settings")}
            style={({ pressed }) => [
              styles.settingsLink,
              pressed ? styles.pressedWide : null
            ]}
          >
            <AppText style={styles.settingsLinkLabel}>Settings</AppText>
          </Pressable>
        </View>

        <TextField
          autoCapitalize="none"
          autoCorrect={false}
          label="Username"
          placeholder="closet.coded"
          value={username}
          onChangeText={setUsername}
        />
        <TextField
          label="Display name"
          placeholder="Malek Ouaida"
          value={displayName}
          onChangeText={setDisplayName}
        />
        <TextField
          label="Style descriptor"
          multiline
          placeholder="Quiet tailoring, sharp essentials, warmer neutrals."
          style={styles.bioInput}
          textAlignVertical="top"
          value={bio}
          onChangeText={setBio}
        />

        {profile.error ? (
          <AppText color={colors.danger} variant="caption">
            {profile.error}
          </AppText>
        ) : null}
        {notice ? (
          <AppText color={colors.success} variant="caption">
            {notice}
          </AppText>
        ) : null}

        <Button
          label="Save Profile"
          loading={profile.isSaving}
          onPress={() => void handleSave()}
        />
      </Card>
    </Screen>
  );
}

function HeroMetric({
  icon,
  label,
  tone,
  value
}: {
  icon: React.ReactNode;
  label: string;
  tone: "blush" | "lavender" | "sage";
  value: string;
}) {
  return (
    <View
      style={[
        styles.heroMetricCard,
        tone === "sage"
          ? styles.heroMetricSage
          : tone === "lavender"
            ? styles.heroMetricLavender
            : styles.heroMetricBlush
      ]}
    >
      <View style={styles.heroMetricIcon}>{icon}</View>
      <AppText style={styles.heroMetricValue}>{value}</AppText>
      <AppText style={styles.heroMetricLabel}>{label}</AppText>
    </View>
  );
}

function SectionHeader({
  actionLabel,
  onPress,
  title
}: {
  actionLabel: string;
  onPress: () => void;
  title: string;
}) {
  return (
    <View style={styles.sectionHeader}>
      <AppText style={styles.sectionTitle}>{title}</AppText>
      <Pressable onPress={onPress}>
        <AppText style={styles.sectionAction}>{actionLabel}</AppText>
      </Pressable>
    </View>
  );
}

function EmptyProfileCard({
  actionLabel,
  copy,
  icon,
  onPress,
  title
}: {
  actionLabel: string;
  copy: string;
  icon: keyof typeof Feather.glyphMap;
  onPress: () => void;
  title: string;
}) {
  return (
    <View style={[styles.emptyCard, featureShadows.sm]}>
      <View style={styles.emptyIcon}>
        <Feather color={featurePalette.muted} name={icon} size={18} />
      </View>
      <AppText style={styles.emptyTitle}>{title}</AppText>
      <AppText style={styles.emptyCopy}>{copy}</AppText>
      <Pressable onPress={onPress} style={styles.emptyAction}>
        <AppText style={styles.emptyActionLabel}>{actionLabel}</AppText>
      </Pressable>
    </View>
  );
}

function SignalCard({
  icon,
  label,
  tone,
  value
}: {
  icon: React.ReactNode;
  label: string;
  tone: "blush" | "lavender" | "sage" | "sky";
  value: string;
}) {
  return (
    <View
      style={[
        styles.signalCard,
        tone === "sage"
          ? styles.signalCardSage
          : tone === "lavender"
            ? styles.signalCardLavender
            : tone === "sky"
              ? styles.signalCardSky
              : styles.signalCardBlush,
        featureShadows.sm
      ]}
    >
      <View style={styles.signalIcon}>{icon}</View>
      <AppText numberOfLines={1} style={styles.signalValue}>
        {value}
      </AppText>
      <AppText style={styles.signalLabel}>{label}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 24,
    paddingBottom: 132
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  topActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  signOutPill: {
    height: 40,
    paddingHorizontal: 16,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.88)",
    alignItems: "center",
    justifyContent: "center"
  },
  signOutLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  heroCard: {
    position: "relative",
    overflow: "hidden",
    borderRadius: 32,
    padding: 24,
    gap: 20
  },
  heroGlowTop: {
    position: "absolute",
    top: -40,
    right: -50,
    width: 180,
    height: 180,
    borderRadius: 90,
    backgroundColor: "rgba(255,255,255,0.46)"
  },
  heroGlowBottom: {
    position: "absolute",
    bottom: -54,
    left: -36,
    width: 152,
    height: 152,
    borderRadius: 76,
    backgroundColor: "rgba(216, 235, 207, 0.4)"
  },
  heroBadgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  heroRow: {
    flexDirection: "row",
    gap: 16,
    alignItems: "center"
  },
  avatarShell: {
    width: 92,
    height: 92,
    borderRadius: 46,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 4,
    borderColor: "rgba(255,255,255,0.7)"
  },
  avatarLabel: {
    ...featureTypography.title,
    color: featurePalette.foreground
  },
  heroCopy: {
    flex: 1,
    gap: 4
  },
  heroTitle: {
    ...featureTypography.display,
    fontSize: 30,
    lineHeight: 34
  },
  heroHandle: {
    ...featureTypography.label,
    color: featurePalette.foreground
  },
  heroDescriptor: {
    ...featureTypography.body,
    color: featurePalette.foreground
  },
  heroStatsRow: {
    flexDirection: "row",
    gap: 10
  },
  heroMetricCard: {
    flex: 1,
    borderRadius: 22,
    paddingHorizontal: 14,
    paddingVertical: 14,
    gap: 4
  },
  heroMetricSage: {
    backgroundColor: "rgba(216, 235, 207, 0.72)"
  },
  heroMetricLavender: {
    backgroundColor: "rgba(232, 219, 255, 0.76)"
  },
  heroMetricBlush: {
    backgroundColor: "rgba(255, 234, 242, 0.82)"
  },
  heroMetricIcon: {
    marginBottom: 2
  },
  heroMetricValue: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 24,
    lineHeight: 26,
    color: featurePalette.foreground
  },
  heroMetricLabel: {
    ...featureTypography.label,
    color: featurePalette.foreground
  },
  heroActionRow: {
    flexDirection: "row",
    gap: 10
  },
  heroPrimaryAction: {
    flex: 1,
    minHeight: 54,
    borderRadius: 20,
    backgroundColor: featurePalette.foreground,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 18
  },
  heroPrimaryActionLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: "#FFFFFF"
  },
  heroSecondaryAction: {
    minWidth: 112,
    minHeight: 54,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.86)",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 16
  },
  heroSecondaryActionLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  segmentRow: {
    gap: 8
  },
  segment: {
    height: 42,
    paddingHorizontal: 16,
    borderRadius: 999,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  segmentActive: {
    backgroundColor: featurePalette.foreground
  },
  segmentLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.muted
  },
  segmentLabelActive: {
    color: "#FFFFFF"
  },
  section: {
    gap: 14
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12
  },
  sectionTitle: {
    ...featureTypography.title,
    fontSize: 26,
    lineHeight: 30
  },
  sectionAction: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  looksRow: {
    gap: 12,
    paddingRight: 4
  },
  lookCard: {
    width: 224,
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    overflow: "hidden"
  },
  lookImageFrame: {
    height: 228,
    backgroundColor: featurePalette.secondary
  },
  lookImage: {
    width: "100%",
    height: "100%"
  },
  lookImagePlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  lookCardCopy: {
    padding: 16,
    gap: 4
  },
  lookCardTitle: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 24,
    lineHeight: 28,
    color: featurePalette.foreground
  },
  lookCardMeta: {
    ...featureTypography.label
  },
  lookCardNote: {
    ...featureTypography.body,
    fontSize: 14,
    lineHeight: 20
  },
  calendarCard: {
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    padding: 18,
    gap: 18
  },
  calendarHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12
  },
  calendarTitle: {
    ...featureTypography.bodyStrong,
    color: featurePalette.foreground
  },
  calendarSubtitle: {
    ...featureTypography.label,
    marginTop: 4
  },
  calendarStreakPill: {
    height: 34,
    paddingHorizontal: 12,
    borderRadius: 999,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255, 234, 242, 0.9)"
  },
  calendarStreakLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  calendarGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10
  },
  calendarDay: {
    width: "13.2%",
    minWidth: 44,
    aspectRatio: 0.88,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    backgroundColor: featurePalette.secondary
  },
  calendarDayFilled: {
    backgroundColor: featurePalette.foreground
  },
  calendarDayToday: {
    borderWidth: 2,
    borderColor: featurePalette.coral
  },
  calendarDayLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.muted
  },
  calendarDayNumber: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 18,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  calendarDayLabelFilled: {
    color: "#FFFFFF"
  },
  savedGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12
  },
  savedCard: {
    width: "47%"
  },
  savedImageFrame: {
    aspectRatio: 3 / 4,
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 8,
    position: "relative"
  },
  savedImage: {
    width: "100%",
    height: "100%"
  },
  savedBadge: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.88)",
    alignItems: "center",
    justifyContent: "center"
  },
  savedTitle: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  savedMeta: {
    ...featureTypography.label,
    marginTop: 2
  },
  signalGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12
  },
  signalCard: {
    width: "47%",
    borderRadius: 22,
    padding: 16,
    gap: 6
  },
  signalCardSage: {
    backgroundColor: "rgba(216, 235, 207, 0.72)"
  },
  signalCardLavender: {
    backgroundColor: "rgba(232, 219, 255, 0.76)"
  },
  signalCardSky: {
    backgroundColor: "rgba(220, 234, 247, 0.82)"
  },
  signalCardBlush: {
    backgroundColor: "rgba(255, 234, 242, 0.82)"
  },
  signalIcon: {
    marginBottom: 4
  },
  signalValue: {
    fontFamily: "Newsreader_600SemiBold",
    fontSize: 24,
    lineHeight: 28,
    color: featurePalette.foreground
  },
  signalLabel: {
    ...featureTypography.label,
    color: featurePalette.foreground
  },
  emptyCard: {
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    padding: 20,
    alignItems: "flex-start",
    gap: 10
  },
  emptyIcon: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: featurePalette.secondary
  },
  emptyTitle: {
    ...featureTypography.bodyStrong,
    color: featurePalette.foreground
  },
  emptyCopy: {
    ...featureTypography.body
  },
  emptyAction: {
    height: 38,
    paddingHorizontal: 16,
    borderRadius: 999,
    backgroundColor: featurePalette.foreground,
    alignItems: "center",
    justifyContent: "center"
  },
  emptyActionLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 13,
    lineHeight: 16,
    color: "#FFFFFF"
  },
  formCard: {
    gap: spacing.md
  },
  formHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: spacing.md
  },
  settingsLink: {
    height: 34,
    paddingHorizontal: 14,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  },
  settingsLinkLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 12,
    lineHeight: 16,
    color: colors.text
  },
  bioInput: {
    minHeight: 108,
    paddingTop: spacing.md
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
