import { Feather } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import { Animated, Pressable, StyleSheet, View } from "react-native";

import {
  EditorialBackButton,
  EditorialPrimaryButton,
  EditorialScreen,
  EditorialTextField,
  buildFadeUpStyle,
  buildScaleInStyle,
  editorialPalette,
  useEditorialIntro
} from "../../src/auth/editorial";
import { fontFamilies } from "../../src/theme";
import { AppText } from "../../src/ui";

export default function ForgotPasswordScreen() {
  const intro = useEditorialIntro(4);
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const isValid = email.includes("@");

  return (
    <EditorialScreen scrollable={false}>
      <View style={styles.page}>
      <Animated.View style={buildFadeUpStyle(intro[0], -8)}>
        <EditorialBackButton onPress={() => router.replace("/login")} variant="surface" />
      </Animated.View>

      {!sent ? (
        <>
          <Animated.View style={[styles.titleBlock, buildFadeUpStyle(intro[1])]}>
            <AppText style={styles.title}>Reset your{"\n"}password</AppText>
            <AppText color={editorialPalette.muted} style={styles.subtitle}>
              Enter your email and we&apos;ll send you a link to get back in.
            </AppText>
          </Animated.View>

          <Animated.View style={[styles.formBlock, buildFadeUpStyle(intro[2])]}>
            <EditorialTextField
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              label="Email"
              leftIcon={<Feather color={editorialPalette.muted} name="mail" size={18} />}
              placeholder="Your email"
              value={email}
              onChangeText={setEmail}
            />
          </Animated.View>

          <Animated.View style={[styles.ctaBlock, buildFadeUpStyle(intro[3], 20)]}>
            <EditorialPrimaryButton
              disabled={!isValid}
              label="Send reset link"
              onPress={() => setSent(true)}
              style={styles.fullWidthButton}
            />
          </Animated.View>
        </>
      ) : (
        <Animated.View style={[styles.successState, buildScaleInStyle(intro[3])]}>
          <View style={styles.successIcon}>
            <Feather color={editorialPalette.text} name="check" size={28} />
          </View>
          <AppText style={styles.successTitle}>Check your inbox</AppText>
          <AppText color={editorialPalette.muted} style={styles.successBody}>
            We sent a reset link to{"\n"}
            <AppText color={editorialPalette.text} style={styles.successEmail}>
              {email}
            </AppText>
          </AppText>
          <Pressable
            onPress={() => router.replace("/login")}
            style={({ pressed }) => [pressed ? styles.pressed : null]}
          >
            <View style={styles.secondaryButton}>
              <AppText style={styles.secondaryButtonLabel}>Back to sign in</AppText>
            </View>
          </Pressable>
        </Animated.View>
      )}
      </View>
    </EditorialScreen>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1
  },
  titleBlock: {
    marginTop: 28,
    gap: 12
  },
  title: {
    fontFamily: fontFamilies.serifSemiBold,
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
    marginTop: 40
  },
  ctaBlock: {
    marginTop: "auto",
    paddingBottom: 40
  },
  fullWidthButton: {
    width: "100%"
  },
  successState: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20
  },
  successIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 24,
    backgroundColor: "rgba(255, 221, 210, 0.45)"
  },
  successTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 26,
    lineHeight: 32,
    textAlign: "center"
  },
  successBody: {
    marginTop: 8,
    marginBottom: 32,
    textAlign: "center",
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 24
  },
  successEmail: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 24
  },
  secondaryButton: {
    minHeight: 48,
    paddingHorizontal: 28,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: editorialPalette.surface,
    shadowColor: editorialPalette.shadow,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 1,
    shadowRadius: 16,
    elevation: 4
  },
  secondaryButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 20
  },
  pressed: {
    opacity: 0.72,
    transform: [{ scale: 0.98 }]
  }
});
