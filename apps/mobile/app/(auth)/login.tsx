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

export default function LoginScreen() {
  const { loginWithPassword } = useAuth();
  const intro = useAuthIntroAnimation(6);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isValid = email.trim().length > 0 && password.length > 0;

  async function handleSubmit() {
    setIsSubmitting(true);
    setError(null);

    const result = await loginWithPassword(email, password);
    setIsSubmitting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    router.replace("/" as Href);
  }

  return (
    <AuthScreen scrollable={false}>
      <View style={styles.page}>
        <Animated.View style={buildFadeUpStyle(intro[0], -8)}>
          <AuthBackButton onPress={() => router.back()} />
        </Animated.View>

        <Animated.View style={[styles.titleBlock, buildFadeUpStyle(intro[1])]}>
          <AppText style={styles.title}>Welcome back</AppText>
          <AppText color={authPalette.muted} style={styles.subtitle}>
            Pick up where you left off.
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
              autoComplete="password"
              label="Password"
              placeholder="••••••••"
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
          </Animated.View>
        </View>

        <Animated.View style={[styles.forgotRow, buildFadeUpStyle(intro[4], 10)]}>
          <Pressable
            onPress={() => router.push("/forgot-password" as Href)}
            style={styles.forgotLinkPressable}
          >
            <AppText color={authPalette.subtle} style={styles.forgotLink}>
              Forgot password?
            </AppText>
          </Pressable>
        </Animated.View>

        <Animated.View style={[styles.ctaBlock, buildFadeUpStyle(intro[5], 20)]}>
          {error ? (
            <AppText color={colors.danger} style={styles.feedbackText}>
              {error}
            </AppText>
          ) : null}
          <AuthPrimaryButton
            disabled={!isValid}
            label="Sign In"
            loading={isSubmitting}
            onPress={() => void handleSubmit()}
          />
          <AuthFooterLink
            label="Create an account"
            onPress={() => router.push("/register")}
            prefix="New here?"
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
  forgotRow: {
    marginTop: 16
  },
  forgotLinkPressable: {
    alignSelf: "flex-start"
  },
  forgotLink: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
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
