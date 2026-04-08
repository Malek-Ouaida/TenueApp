import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { useAuth } from "../src/auth/provider";
import {
  EditorialPrimaryButton,
  EditorialScreen,
  EditorialTextField,
  buildFadeUpStyle,
  buildScaleInStyle,
  editorialPalette,
  useEditorialIntro
} from "../src/auth/editorial";
import { useProfile } from "../src/profile/hooks";
import { fontFamilies } from "../src/theme";
import { AppText } from "../src/ui";

function normalizeOptionalField(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export default function ProfileSetupScreen() {
  const { logoutCurrentUser, session } = useAuth();
  const intro = useEditorialIntro(6);
  const profile = useProfile({
    accessToken: session?.access_token,
    onUnauthorized: async () => {
      await logoutCurrentUser();
      router.replace("/login");
    }
  });
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [didHydrateProfile, setDidHydrateProfile] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const avatarBreath = useRef(new Animated.Value(0)).current;
  const sparkle = useRef(new Animated.Value(0)).current;
  const orbFloat = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const avatarLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(avatarBreath, {
          toValue: 1,
          duration: 2000,
          useNativeDriver: true
        }),
        Animated.timing(avatarBreath, {
          toValue: 0,
          duration: 2000,
          useNativeDriver: true
        })
      ])
    );
    const sparkleLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(sparkle, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true
        }),
        Animated.timing(sparkle, {
          toValue: 0,
          duration: 1000,
          useNativeDriver: true
        })
      ])
    );
    const orbLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(orbFloat, {
          toValue: 1,
          duration: 6000,
          useNativeDriver: true
        }),
        Animated.timing(orbFloat, {
          toValue: 0,
          duration: 6000,
          useNativeDriver: true
        })
      ])
    );

    avatarLoop.start();
    sparkleLoop.start();
    orbLoop.start();

    return () => {
      avatarLoop.stop();
      sparkleLoop.stop();
      orbLoop.stop();
    };
  }, [avatarBreath, orbFloat, sparkle]);

  useEffect(() => {
    if (didHydrateProfile || profile.isLoading) {
      return;
    }

    setUsername((current) => current || (profile.profile?.username ?? ""));
    setDisplayName((current) => current || (profile.profile?.display_name ?? ""));
    setDidHydrateProfile(true);
  }, [didHydrateProfile, profile.isLoading, profile.profile?.display_name, profile.profile?.username]);

  async function handleContinue() {
    setError(null);

    const nextProfile = await profile.saveProfile({
      username: normalizeOptionalField(username),
      display_name: normalizeOptionalField(displayName)
    });

    if (!nextProfile) {
      setError(profile.error ?? "Profile setup could not be saved.");
      return;
    }

    router.replace("/");
  }

  const hasInput = username.trim().length > 0 || displayName.trim().length > 0;

  return (
    <EditorialScreen
      backgroundDecor={
        <View style={styles.topAccent}>
          <Animated.View
            style={[
              styles.topAccentOrb,
              {
                transform: [
                  {
                    translateX: orbFloat.interpolate({
                      inputRange: [0, 1],
                      outputRange: [0, -18]
                    })
                  },
                  {
                    translateY: orbFloat.interpolate({
                      inputRange: [0, 1],
                      outputRange: [0, 14]
                    })
                  }
                ]
              }
            ]}
          />
        </View>
      }
    >
      <View style={styles.page}>
        <Animated.View style={[styles.titleRow, buildFadeUpStyle(intro[0])]}>
          <View style={styles.titleWithIcon}>
            <AppText style={styles.title}>Make it yours</AppText>
            <Animated.View
              style={{
                opacity: sparkle.interpolate({
                  inputRange: [0, 0.5, 1],
                  outputRange: [1, 0.6, 1]
                }),
                transform: [
                  {
                    rotate: sparkle.interpolate({
                      inputRange: [0, 0.5, 1],
                      outputRange: ["0deg", "15deg", "0deg"]
                    })
                  },
                  {
                    scale: sparkle.interpolate({
                      inputRange: [0, 0.5, 1],
                      outputRange: [1, 0.9, 1]
                    })
                  }
                ]
              }}
            >
              <Ionicons color={editorialPalette.accent} name="sparkles" size={18} />
            </Animated.View>
          </View>
        </Animated.View>

        <Animated.View style={[styles.avatarRow, buildScaleInStyle(intro[1])]}>
          <View style={styles.avatarButton}>
            <Animated.View
              style={[
                styles.avatarShell,
                {
                  transform: [
                    {
                      scale: avatarBreath.interpolate({
                        inputRange: [0, 0.5, 1],
                        outputRange: [1, 1.02, 1]
                      })
                    }
                  ],
                  shadowOpacity: avatarBreath.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [0.1, 0.18, 0.1]
                  })
                }
              ]}
            >
              <Ionicons color={editorialPalette.accentSoft} name="camera-outline" size={28} />
            </Animated.View>
            <LinearGradient
              colors={[editorialPalette.accent, editorialPalette.accentSoft]}
              end={{ x: 1, y: 1 }}
              start={{ x: 0, y: 0 }}
              style={styles.avatarBadge}
            >
              <AppText style={styles.avatarBadgeText}>+</AppText>
            </LinearGradient>
          </View>
        </Animated.View>

        <View style={styles.formBlock}>
          <View>
            <EditorialTextField
              autoCapitalize="none"
              autoCorrect={false}
              label="Username"
              placeholder="@yourname"
              value={username}
              onChangeText={setUsername}
            />
          </View>

          <View>
            <EditorialTextField
              autoCorrect={false}
              label="Display name"
              placeholder="Your name"
              value={displayName}
              onChangeText={setDisplayName}
            />
          </View>

          <Animated.View style={buildFadeUpStyle(intro[4], 10)}>
            <AppText color={editorialPalette.subtle} style={styles.microcopy}>
              You can always change this later.
            </AppText>
          </Animated.View>
        </View>

        <Animated.View style={[styles.ctaBlock, buildFadeUpStyle(intro[5], 20)]}>
          {error ? (
            <AppText color="#B05246" style={styles.feedbackText}>
              {error}
            </AppText>
          ) : profile.error ? (
            <AppText color="#B05246" style={styles.feedbackText}>
              {profile.error}
            </AppText>
          ) : null}
          <EditorialPrimaryButton
            disabled={!hasInput}
            label="Continue"
            loading={profile.isSaving}
            onPress={() => void handleContinue()}
          />
        </Animated.View>
      </View>
    </EditorialScreen>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1
  },
  topAccent: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 220,
    overflow: "hidden"
  },
  topAccentOrb: {
    position: "absolute",
    width: 300,
    height: 300,
    top: -100,
    right: -50,
    borderRadius: 999,
    backgroundColor: "rgba(255, 221, 210, 0.34)"
  },
  titleRow: {
    marginTop: 66
  },
  titleWithIcon: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  title: {
    fontFamily: fontFamilies.serifMedium,
    fontSize: 32,
    lineHeight: 38,
    letterSpacing: -0.64
  },
  avatarRow: {
    marginTop: 40,
    alignItems: "center"
  },
  avatarButton: {
    position: "relative"
  },
  avatarShell: {
    width: 120,
    height: 120,
    borderRadius: 60,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: editorialPalette.accentSurface,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: editorialPalette.accentLine,
    shadowColor: editorialPalette.accent,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 5
  },
  avatarBadge: {
    position: "absolute",
    right: -2,
    bottom: -2,
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: editorialPalette.accent
  },
  avatarBadgeText: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 18,
    lineHeight: 18,
    color: "#FFFFFF"
  },
  formBlock: {
    marginTop: 40,
    gap: 20
  },
  ctaBlock: {
    marginTop: "auto",
    paddingBottom: 40,
    gap: 14
  },
  microcopy: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 18
  },
  feedbackText: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
  }
});
