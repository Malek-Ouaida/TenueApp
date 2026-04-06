import { router, type Href } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import * as Haptics from "expo-haptics";

import { useAuth } from "../../../src/auth/provider";
import { useReviewQueue } from "../../../src/closet/hooks";
import { useClosetInsights } from "../../../src/closet/insights";
import { useProfile } from "../../../src/profile/hooks";
import { colors, radius, spacing } from "../../../src/theme";
import {
  AppText,
  BrandMark,
  Button,
  Card,
  Chip,
  Screen,
  TextField
} from "../../../src/ui";

type ProfileSectionKey = "looks" | "wear" | "saved" | "insights";

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

  async function handleSave() {
    const nextProfile = await profile.saveProfile({
      username: normalizeOptionalField(username),
      display_name: normalizeOptionalField(displayName),
      bio: normalizeOptionalField(bio)
    });

    if (!nextProfile) {
      return;
    }

    await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    setNotice("Profile saved.");
  }

  async function handleLogout() {
    await logoutCurrentUser();
    router.replace("/login");
  }

  const initials = (profile.profile?.display_name ?? user?.email ?? "T")
    .split(/[\s._@-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0]?.toUpperCase() ?? "")
    .join("") || "T";
  const descriptor =
    profile.profile?.bio ??
    (insights.insights.topColor
      ? `A closet leaning ${insights.insights.topColor.label.toLowerCase()} and ${insights.insights.topCategory?.label?.toLowerCase() ?? "sharp basics"}.`
      : "Building a sharper wardrobe system.");
  const needsReviewCount =
    reviewQueue.sections.find((section) => section.key === "needs_review")?.items.length ?? 0;
  const processedCoverage =
    insights.insights.totalItems === 0
      ? "0%"
      : `${Math.round((insights.insights.processedItems / insights.insights.totalItems) * 100)}%`;

  return (
    <Screen>
      <View style={styles.topRow}>
        <BrandMark variant="wordmark" subtle />
        <Button label="Sign Out" onPress={() => void handleLogout()} size="sm" variant="ghost" />
      </View>

      <Card tone="soft" style={styles.heroCard}>
        <View style={styles.heroRow}>
          <View style={styles.avatar}>
            <AppText variant="title">{initials}</AppText>
          </View>
          <View style={styles.heroCopy}>
            <Chip label="Private identity" tone="organize" />
            <AppText variant="title">
              {profile.profile?.display_name ?? "Set your fashion identity"}
            </AppText>
            <AppText color={colors.textMuted}>
              {profile.profile?.username ? `@${profile.profile.username}` : "Claim your username"}
            </AppText>
            <AppText color={colors.textMuted}>{descriptor}</AppText>
          </View>
        </View>
      </Card>

      <View style={styles.statsRow}>
        <StatCard label="Closet items" value={`${insights.insights.totalItems}`} />
        <StatCard label="Needs review" value={`${needsReviewCount}`} tone="review" />
        <StatCard label="Processed" value={processedCoverage} tone="positive" />
        <StatCard
          label="Top category"
          value={insights.insights.topCategory?.label ?? "Waiting"}
          tone="organize"
        />
      </View>

      <View style={styles.segmentRow}>
        {[
          { key: "looks", label: "Looks" },
          { key: "wear", label: "Wear Log" },
          { key: "saved", label: "Saved" },
          { key: "insights", label: "Insights" }
        ].map((segment) => {
          const active = selectedSection === segment.key;

          return (
            <Pressable
              key={segment.key}
              onPress={() => setSelectedSection(segment.key as ProfileSectionKey)}
              style={[styles.segment, active ? styles.segmentActive : null]}
            >
              <AppText
                color={active ? colors.text : colors.textSubtle}
                variant="captionStrong"
              >
                {segment.label}
              </AppText>
            </Pressable>
          );
        })}
      </View>

      <ProfileSection
        profileSection={selectedSection}
        topCategory={insights.insights.topCategory?.label ?? null}
        topColor={insights.insights.topColor?.label ?? null}
      />

      <Card tone="soft" style={styles.formCard}>
        <AppText color={colors.textSubtle} variant="eyebrow">
          Edit Profile
        </AppText>
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
        <Button label="Save Profile" loading={profile.isSaving} onPress={() => void handleSave()} />
      </Card>

      <Pressable onPress={() => router.push("/insights" as Href)}>
        <Card tone="organize">
          <AppText color={colors.textSubtle} variant="eyebrow">
            Wardrobe intelligence
          </AppText>
          <AppText variant="sectionTitle">Open your full insights dashboard.</AppText>
          <AppText color={colors.textMuted}>
            Category balance, dominant colors, processed coverage, and duplicate watchlists already
            live off current closet contracts.
          </AppText>
        </Card>
      </Pressable>
    </Screen>
  );
}

function ProfileSection({
  profileSection,
  topCategory,
  topColor
}: {
  profileSection: ProfileSectionKey;
  topCategory: string | null;
  topColor: string | null;
}) {
  if (profileSection === "insights") {
    return (
      <Card tone="organize">
        <Chip label="Live from closet data" tone="organize" />
        <AppText variant="sectionTitle">Personal patterns are already forming.</AppText>
        <AppText color={colors.textMuted}>
          {topCategory
            ? `${topCategory} currently leads the wardrobe, with ${topColor?.toLowerCase() ?? "your leading tones"} giving the closet its signature.`
            : "Confirm more items and the wardrobe signature will start to sharpen."}
        </AppText>
      </Card>
    );
  }

  if (profileSection === "saved") {
    return (
      <Card tone="lookbook">
        <Chip label="Future lookbook" tone="lookbook" />
        <AppText variant="sectionTitle">Saved looks will live here.</AppText>
        <AppText color={colors.textMuted}>
          Inspiration saves and favorite styling outcomes stay distinct from the confirmed closet.
        </AppText>
      </Card>
    );
  }

  if (profileSection === "wear") {
    return (
      <Card tone="review">
        <Chip label="Wear history" tone="review" />
        <AppText variant="sectionTitle">Wear logging lands after lookbook foundations.</AppText>
        <AppText color={colors.textMuted}>
          Logged outfits, frequency, and stale-item signals will populate this section once those
          flows are implemented.
        </AppText>
      </Card>
    );
  }

  return (
    <Card tone="lookbook">
      <Chip label="Looks" tone="lookbook" />
      <AppText variant="sectionTitle">Profile is prepared for image-led style history.</AppText>
      <AppText color={colors.textMuted}>
        This first pass gives Tenue a premium identity shell without faking social or gallery
        behaviors that do not exist yet.
      </AppText>
    </Card>
  );
}

function StatCard({
  label,
  tone = "soft",
  value
}: {
  label: string;
  tone?: "soft" | "review" | "positive" | "organize";
  value: string;
}) {
  return (
    <Card shadow={false} style={styles.statCard} tone={tone}>
      <AppText color={colors.textSubtle} variant="caption">
        {label}
      </AppText>
      <AppText numberOfLines={1} variant="bodyStrong">
        {value}
      </AppText>
    </Card>
  );
}

const styles = StyleSheet.create({
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  heroCard: {
    gap: spacing.md
  },
  heroRow: {
    flexDirection: "row",
    gap: spacing.md
  },
  avatar: {
    width: 84,
    height: 84,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.backgroundSoft
  },
  heroCopy: {
    flex: 1,
    gap: spacing.xs
  },
  statsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  statCard: {
    width: "47%",
    gap: spacing.xs
  },
  segmentRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  segment: {
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  },
  segmentActive: {
    backgroundColor: colors.cornflowerSurface,
    borderColor: "rgba(174, 197, 241, 0.62)"
  },
  formCard: {
    gap: spacing.md
  },
  bioInput: {
    minHeight: 108,
    paddingTop: spacing.md
  }
});
