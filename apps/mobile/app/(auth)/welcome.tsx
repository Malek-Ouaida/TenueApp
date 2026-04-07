import { useEffect, useState } from "react";
import { router } from "expo-router";
import { Image } from "expo-image";
import { Animated, Pressable, StyleSheet, useWindowDimensions, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import {
  EditorialPrimaryButton,
  EditorialScreen,
  buildFadeUpStyle,
  editorialPalette,
  useEditorialIntro
} from "../../src/auth/editorial";
import { fontFamilies } from "../../src/theme";
import { AppText } from "../../src/ui";

import tenueWordmark from "../../assets/auth/tenue_black.png";
import welcomeHero from "../../assets/auth/welcome-hero.jpg";

export default function WelcomeScreen() {
  const intro = useEditorialIntro(4);
  const { height } = useWindowDimensions();
  const [ready, setReady] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const heroHeight = Math.max(380, Math.round(height * 0.58));

  useEffect(() => {
    const timer = setTimeout(() => setReady(true), 80);
    return () => clearTimeout(timer);
  }, []);

  return (
    <EditorialScreen contentStyle={styles.screenContent} scrollable={false}>
      <View style={styles.page}>
        <View style={[styles.heroShell, { height: heroHeight }]}>
          <Animated.View
            style={[
              styles.heroMedia,
              {
                opacity: ready && imageLoaded ? 1 : 0,
                transform: [{ scale: ready ? 1 : 1.06 }]
              }
            ]}
          >
            <Image
              contentFit="cover"
              onLoad={() => setImageLoaded(true)}
              source={welcomeHero}
              style={styles.heroImage}
            />
            <LinearGradient
              colors={["transparent", "transparent", editorialPalette.background]}
              locations={[0, 0.4, 0.95]}
              style={StyleSheet.absoluteFillObject}
            />
            <View style={styles.heroVignette} />
          </Animated.View>

          <Animated.View style={[styles.logoWrap, buildFadeUpStyle(intro[0], -12)]}>
            <Image contentFit="contain" source={tenueWordmark} style={styles.logo} />
          </Animated.View>
        </View>

        <View style={styles.content}>
          <Animated.View style={buildFadeUpStyle(intro[1], 20)}>
            <AppText style={styles.headline}>
              See your style{"\n"}
              <AppText style={styles.headlineAccent}>clearly.</AppText>
            </AppText>
          </Animated.View>

          <Animated.View style={[styles.copyWrap, buildFadeUpStyle(intro[2], 16)]}>
            <AppText style={styles.copy}>
              Capture, organize, and understand{"\n"}what you wear - effortlessly.
            </AppText>
          </Animated.View>

          <View style={styles.spacer} />

          <Animated.View style={[styles.ctaArea, buildFadeUpStyle(intro[3], 24)]}>
            <EditorialPrimaryButton
              label="Start your wardrobe"
              onPress={() => router.push("/register")}
              style={styles.fullWidthButton}
            />

            <View style={styles.secondaryActions}>
              <Pressable
                onPress={() => router.push("/login")}
                style={({ pressed }) => [pressed ? styles.pressed : null]}
              >
                <AppText style={styles.signInText}>
                  Already have an account? <AppText style={styles.signInStrong}>Sign in</AppText>
                </AppText>
              </Pressable>
            </View>
          </Animated.View>
        </View>
      </View>
    </EditorialScreen>
  );
}

const styles = StyleSheet.create({
  screenContent: {
    paddingTop: 0,
    paddingBottom: 0,
    paddingHorizontal: 0
  },
  page: {
    flex: 1,
    backgroundColor: editorialPalette.background
  },
  heroShell: {
    position: "relative",
    width: "100%",
    minHeight: 380,
    overflow: "hidden"
  },
  heroMedia: {
    ...StyleSheet.absoluteFillObject
  },
  heroImage: {
    width: "100%",
    height: "100%"
  },
  heroVignette: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "transparent",
    shadowColor: editorialPalette.background,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 90
  },
  logoWrap: {
    position: "absolute",
    top: 56,
    left: 24,
    zIndex: 2
  },
  logo: {
    width: 70,
    height: 20,
    opacity: 0.8
  },
  content: {
    flex: 1,
    marginTop: -16,
    paddingHorizontal: 28
  },
  headline: {
    fontFamily: fontFamilies.serifMedium,
    fontSize: 36,
    lineHeight: 39,
    letterSpacing: -0.72,
    color: editorialPalette.text
  },
  headlineAccent: {
    fontFamily: fontFamilies.serifRegularItalic,
    fontSize: 36,
    lineHeight: 39,
    color: editorialPalette.accent
  },
  copyWrap: {
    marginTop: 16
  },
  copy: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 24,
    letterSpacing: -0.15,
    color: "#64748B"
  },
  spacer: {
    flex: 1,
    minHeight: 32
  },
  ctaArea: {
    paddingBottom: 40,
    gap: 20
  },
  fullWidthButton: {
    width: "100%"
  },
  secondaryActions: {
    alignItems: "center",
    gap: 12
  },
  signInText: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 20,
    letterSpacing: -0.14,
    color: editorialPalette.muted
  },
  signInStrong: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 20,
    color: editorialPalette.text
  },
  pressed: {
    opacity: 0.72,
    transform: [{ scale: 0.98 }]
  }
});
