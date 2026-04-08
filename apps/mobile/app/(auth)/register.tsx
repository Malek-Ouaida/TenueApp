import { Feather } from "@expo/vector-icons";
import { router, type Href } from "expo-router";
import { useState } from "react";
import { Animated, Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../src/auth/provider";
import {
  AuthFooterLink,
  AuthBackButton,
  AuthPrimaryButton,
  AuthScreen,
  AuthTextField,
  buildFadeUpStyle,
  authPalette,
  useAuthIntroAnimation
} from "../../src/auth/ui";
import { colors, fontFamilies } from "../../src/theme";
import { AppText } from "../../src/ui";

export default function RegisterScreen() {
  const { registerWithPassword } = useAuth();
  const intro = useAuthIntroAnimation(7);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isValid = email.trim().length > 0 && password.length >= 6;

  async function handleSubmit() {
    setIsSubmitting(true);
    setError(null);
    setNotice(null);

    const result = await registerWithPassword(email, password);
    setIsSubmitting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    if (result.nextStep === "authenticated") {
      router.replace("/profile-setup" as Href);
      return;
    }

    setPassword("");
    setNotice(result.message);
  }

  return (
    <AuthScreen scrollable={false}>
      <View style={styles.page}>
        <Animated.View style={buildFadeUpStyle(intro[0], -8)}>
          <AuthBackButton onPress={() => router.back()} />
        </Animated.View>

        <Animated.View style={[styles.titleBlock, buildFadeUpStyle(intro[1])]}>
          <AppText style={styles.title}>Create your{"\n"}account</AppText>
          <AppText color={authPalette.muted} style={styles.subtitle}>
            Start building your wardrobe.
          </AppText>
        </Animated.View>

        <View style={styles.formBlock}>
          <Animated.View style={buildFadeUpStyle(intro[2])}>
            <AuthTextField
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              label="Email"
              placeholder="you@example.com"
              value={email}
              onChangeText={setEmail}
            />
          </Animated.View>

          <Animated.View style={buildFadeUpStyle(intro[3])}>
            <AuthTextField
              autoCapitalize="none"
              autoComplete="new-password"
              label="Password"
              placeholder="At least 6 characters"
              rightAccessory={
                <Pressable
                  onPress={() => setShowPassword((current) => !current)}
                  style={({ pressed }) => [pressed ? styles.pressedIcon : null]}
                >
                  <Feather
                    color={authPalette.subtle}
                    name={showPassword ? "eye-off" : "eye"}
                    size={18}
                  />
                </Pressable>
              }
              secureTextEntry={!showPassword}
              value={password}
              onChangeText={setPassword}
            />
            {password.length > 0 ? (
              <View style={styles.passwordStrengthRow}>
                {[1, 2, 3, 4].map((segment) => {
                  const active = password.length >= segment * 3;

                  return (
                    <View
                      key={segment}
                      style={[
                        styles.passwordStrengthSegment,
                        active
                          ? segment === 1
                            ? styles.passwordStrengthWeak
                            : segment === 2
                              ? styles.passwordStrengthMedium
                              : styles.passwordStrengthStrong
                          : styles.passwordStrengthIdle
                      ]}
                    />
                  );
                })}
              </View>
            ) : null}
          </Animated.View>
        </View>

        <Animated.View style={[styles.termsBlock, buildFadeUpStyle(intro[4], 8)]}>
          <AppText color={authPalette.subtle} style={styles.termsText}>
            By continuing, you agree to our Terms of Service and Privacy Policy.
          </AppText>
        </Animated.View>

        <Animated.View style={[styles.ctaBlock, buildFadeUpStyle(intro[5], 20)]}>
          {error ? (
            <AppText color={colors.danger} style={styles.feedbackText}>
              {error}
            </AppText>
          ) : null}
          {notice ? (
            <AppText color={colors.success} style={styles.feedbackText}>
              {notice}
            </AppText>
          ) : null}
          <AuthPrimaryButton
            disabled={!isValid}
            label="Start your wardrobe"
            loading={isSubmitting}
            onPress={() => void handleSubmit()}
          />
          <AuthFooterLink
            label="Sign in"
            onPress={() => router.push("/login")}
            prefix="Already registered?"
          />
        </Animated.View>
      </View>
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1
  },
  titleBlock: {
    marginTop: 28,
    gap: 8
  },
  title: {
    fontFamily: fontFamilies.serifMedium,
    fontSize: 32,
    lineHeight: 38,
    letterSpacing: -0.64
  },
  subtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 22
  },
  formBlock: {
    marginTop: 40,
    gap: 20
  },
  termsBlock: {
    marginTop: 20
  },
  passwordStrengthRow: {
    flexDirection: "row",
    gap: 6,
    marginTop: 12
  },
  passwordStrengthSegment: {
    flex: 1,
    height: 3,
    borderRadius: 999
  },
  passwordStrengthIdle: {
    backgroundColor: authPalette.border
  },
  passwordStrengthWeak: {
    backgroundColor: authPalette.accent
  },
  passwordStrengthMedium: {
    backgroundColor: "#F59E0B"
  },
  passwordStrengthStrong: {
    backgroundColor: "#10B981"
  },
  termsText: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 18
  },
  feedbackText: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
  },
  ctaBlock: {
    marginTop: "auto",
    paddingBottom: 40,
    gap: 14
  },
  pressedIcon: {
    opacity: 0.72,
    transform: [{ scale: 0.96 }]
  }
});
