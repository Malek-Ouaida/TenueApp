import { router } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";

import { useAuth } from "../../src/auth/provider";
import { ApiError } from "../../src/lib/api";
import { getMyProfile, updateMyProfile } from "../../src/profile/client";
import type { Profile } from "../../src/profile/types";

export default function ProfileScreen() {
  const { logoutCurrentUser, session, user } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadProfile() {
      if (!session) {
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const nextProfile = await getMyProfile(session.access_token);
        if (!mounted) {
          return;
        }

        applyProfile(nextProfile);
      } catch (loadError) {
        if (loadError instanceof ApiError && loadError.status === 401) {
          await logoutCurrentUser();
          router.replace("/login");
          return;
        }

        if (!mounted) {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : "Profile could not be loaded.");
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    void loadProfile();

    return () => {
      mounted = false;
    };
  }, [logoutCurrentUser, session?.access_token]);

  async function handleSave() {
    if (!session) {
      return;
    }

    setIsSaving(true);
    setError(null);
    setNotice(null);

    try {
      const nextProfile = await updateMyProfile(session.access_token, {
        username: normalizeOptionalField(username),
        display_name: normalizeOptionalField(displayName),
        bio: normalizeOptionalField(bio)
      });

      applyProfile(nextProfile);
      setNotice("Profile saved.");
    } catch (saveError) {
      if (saveError instanceof ApiError && saveError.status === 401) {
        await logoutCurrentUser();
        router.replace("/login");
        return;
      }

      setError(saveError instanceof Error ? saveError.message : "Profile update failed.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleLogout() {
    await logoutCurrentUser();
    router.replace("/login");
  }

  function applyProfile(nextProfile: Profile) {
    setProfile(nextProfile);
    setUsername(nextProfile.username ?? "");
    setDisplayName(nextProfile.display_name ?? "");
    setBio(nextProfile.bio ?? "");
  }

  if (isLoading) {
    return (
      <View style={styles.loadingScreen}>
        <StatusBar style="dark" />
        <ActivityIndicator color="#1f1a15" size="large" />
        <Text style={styles.loadingCopy}>Loading your profile shell…</Text>
      </View>
    );
  }

  const heroName = profile?.display_name ?? "Add a display name";
  const heroHandle = profile?.username ? `@${profile.username}` : "Claim your username";
  const heroBio =
    profile?.bio ??
    "This shell is ready for your identity now, and for lookbook and stats surfaces later.";
  const initials = getInitials(profile, user?.email ?? "");

  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.screen}>
      <StatusBar style="dark" />

      <View style={styles.heroCard}>
        <View style={styles.heroRow}>
          <View style={styles.avatarFrame}>
            {profile?.avatar_url ? (
              <Image source={{ uri: profile.avatar_url }} style={styles.avatarImage} />
            ) : (
              <Text style={styles.avatarFallback}>{initials}</Text>
            )}
          </View>

          <View style={styles.heroCopy}>
            <View style={styles.heroTopline}>
              <Text style={styles.eyebrow}>Profile foundation</Text>
              <Text style={styles.badge}>Private shell</Text>
            </View>

            <Text style={styles.heroHandle}>{heroHandle}</Text>
            <Text style={styles.heroName}>{heroName}</Text>
            <Text style={styles.heroBio}>{heroBio}</Text>
          </View>
        </View>

        <View style={styles.metaRow}>
          <Text style={styles.metaPill}>{user?.email ?? "Unknown email"}</Text>
          <Text style={styles.metaPill}>
            {profile?.username ? `/u/${profile.username}` : "Route unlocks after username claim"}
          </Text>
        </View>
      </View>

      <View style={styles.panel}>
        <View style={styles.panelHeader}>
          <View>
            <Text style={styles.eyebrow}>Edit identity</Text>
            <Text style={styles.panelTitle}>Own the profile shell</Text>
          </View>
          <Pressable style={styles.ghostButton} onPress={() => void handleLogout()}>
            <Text style={styles.ghostButtonLabel}>Sign out</Text>
          </Pressable>
        </View>

        <Text style={styles.label}>Username</Text>
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="closet.coded"
          placeholderTextColor="#8b7e70"
          style={styles.input}
          value={username}
          onChangeText={setUsername}
        />
        <Text style={styles.helper}>Lowercase letters, numbers, periods, and underscores only.</Text>

        <Text style={styles.label}>Display name</Text>
        <TextInput
          placeholder="Malek Ouaida"
          placeholderTextColor="#8b7e70"
          style={styles.input}
          value={displayName}
          onChangeText={setDisplayName}
        />

        <Text style={styles.label}>Bio</Text>
        <TextInput
          multiline
          placeholder="Building a sharper wardrobe system."
          placeholderTextColor="#8b7e70"
          style={[styles.input, styles.textarea]}
          textAlignVertical="top"
          value={bio}
          onChangeText={setBio}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}
        {notice ? <Text style={styles.notice}>{notice}</Text> : null}

        <Pressable style={styles.primaryButton} onPress={() => void handleSave()} disabled={isSaving}>
          {isSaving ? (
            <ActivityIndicator color="#fcfaf6" />
          ) : (
            <Text style={styles.primaryButtonLabel}>Save profile</Text>
          )}
        </Pressable>
      </View>

      <View style={styles.panel}>
        <Text style={styles.eyebrow}>Profile surface</Text>
        <Text style={styles.panelTitle}>Header first, content later</Text>
        <Text style={styles.panelCopy}>
          This phase only prepares the structure. Lookbook, stats, and insights remain placeholder
          sections until those domains exist.
        </Text>

        <View style={styles.placeholderCard}>
          <Text style={styles.placeholderTitle}>Lookbook</Text>
          <Text style={styles.placeholderCopy}>
            Reserved for outfit logs and image-first personal history.
          </Text>
        </View>

        <View style={styles.placeholderCard}>
          <Text style={styles.placeholderTitle}>Stats</Text>
          <Text style={styles.placeholderCopy}>
            Reserved for wear data, closet intelligence, and profile insights.
          </Text>
        </View>
      </View>

      <View style={styles.panel}>
        <Text style={styles.eyebrow}>Grid preview</Text>
        <Text style={styles.panelTitle}>Prepared for image-led modules</Text>

        <View style={styles.mosaicGrid}>
          <View style={[styles.mosaicTile, styles.mosaicTileLarge]}>
            <Text style={styles.mosaicLabel}>Hero lookbook slot</Text>
          </View>
          <View style={styles.mosaicTile}>
            <Text style={styles.mosaicLabel}>Closet stats</Text>
          </View>
          <View style={styles.mosaicTile}>
            <Text style={styles.mosaicLabel}>Saved looks</Text>
          </View>
          <View style={styles.mosaicTile}>
            <Text style={styles.mosaicLabel}>Insights</Text>
          </View>
          <View style={styles.mosaicTile}>
            <Text style={styles.mosaicLabel}>Recent activity</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

function normalizeOptionalField(value: string): string | null {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function getInitials(profile: Profile | null, email: string): string {
  const source = profile?.display_name ?? profile?.username ?? email;

  return source
    .split(/[\s._@-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0]?.toUpperCase() ?? "")
    .join("") || "T";
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#f6f2eb"
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 36,
    gap: 16
  },
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    backgroundColor: "#f6f2eb"
  },
  loadingCopy: {
    color: "#564b3f",
    fontSize: 16
  },
  heroCard: {
    padding: 18,
    borderRadius: 28,
    borderWidth: 1,
    borderColor: "rgba(31, 26, 21, 0.08)",
    backgroundColor: "rgba(255, 255, 255, 0.86)"
  },
  heroRow: {
    flexDirection: "row",
    gap: 16
  },
  avatarFrame: {
    width: 86,
    height: 86,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    backgroundColor: "#1f1a15"
  },
  avatarImage: {
    width: "100%",
    height: "100%"
  },
  avatarFallback: {
    color: "#fcfaf6",
    fontSize: 28,
    fontWeight: "700"
  },
  heroCopy: {
    flex: 1,
    gap: 8
  },
  heroTopline: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12
  },
  eyebrow: {
    color: "#8b6f48",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.8,
    textTransform: "uppercase"
  },
  badge: {
    color: "#564b3f",
    fontSize: 12,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: "rgba(31, 26, 21, 0.06)"
  },
  heroHandle: {
    color: "#1f1a15",
    fontSize: 30,
    fontWeight: "700"
  },
  heroName: {
    color: "#8b6f48",
    fontSize: 16,
    fontWeight: "700"
  },
  heroBio: {
    color: "#564b3f",
    fontSize: 15,
    lineHeight: 23
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 14
  },
  metaPill: {
    color: "#564b3f",
    fontSize: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "rgba(31, 26, 21, 0.06)"
  },
  panel: {
    padding: 18,
    borderRadius: 26,
    borderWidth: 1,
    borderColor: "rgba(31, 26, 21, 0.08)",
    backgroundColor: "rgba(255, 255, 255, 0.84)",
    gap: 12
  },
  panelHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12
  },
  panelTitle: {
    color: "#1f1a15",
    fontSize: 24,
    fontWeight: "700"
  },
  panelCopy: {
    color: "#564b3f",
    fontSize: 15,
    lineHeight: 23
  },
  label: {
    marginTop: 4,
    color: "#8b6f48",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.4,
    textTransform: "uppercase"
  },
  input: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(31, 26, 21, 0.08)",
    backgroundColor: "rgba(255, 255, 255, 0.92)",
    paddingHorizontal: 16,
    paddingVertical: 15,
    color: "#1f1a15",
    fontSize: 16
  },
  textarea: {
    minHeight: 110
  },
  helper: {
    color: "#564b3f",
    fontSize: 13,
    lineHeight: 20
  },
  error: {
    color: "#a53f33",
    fontSize: 14,
    lineHeight: 20
  },
  notice: {
    color: "#2f6f54",
    fontSize: 14,
    lineHeight: 20
  },
  primaryButton: {
    marginTop: 4,
    minHeight: 56,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 18,
    backgroundColor: "#1f1a15"
  },
  primaryButtonLabel: {
    color: "#fcfaf6",
    fontSize: 16,
    fontWeight: "700"
  },
  ghostButton: {
    minHeight: 40,
    paddingHorizontal: 14,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 14,
    backgroundColor: "rgba(31, 26, 21, 0.08)"
  },
  ghostButtonLabel: {
    color: "#1f1a15",
    fontSize: 14,
    fontWeight: "700"
  },
  placeholderCard: {
    padding: 14,
    borderRadius: 18,
    backgroundColor: "rgba(31, 26, 21, 0.04)",
    borderWidth: 1,
    borderColor: "rgba(31, 26, 21, 0.05)"
  },
  placeholderTitle: {
    color: "#1f1a15",
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 6
  },
  placeholderCopy: {
    color: "#564b3f",
    fontSize: 14,
    lineHeight: 21
  },
  mosaicGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10
  },
  mosaicTile: {
    width: "48%",
    minHeight: 120,
    borderRadius: 22,
    padding: 14,
    justifyContent: "flex-end",
    backgroundColor: "#7f6540"
  },
  mosaicTileLarge: {
    width: "100%",
    minHeight: 160,
    backgroundColor: "#1f1a15"
  },
  mosaicLabel: {
    color: "#fcfaf6",
    fontSize: 15,
    fontWeight: "700"
  }
});
