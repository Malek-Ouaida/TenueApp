import { StyleSheet } from "react-native";

import { colors, fontFamilies } from "../theme";

export const featurePalette = {
  background: colors.cream,
  card: colors.warmWhite,
  darkText: "#0F172A",
  foreground: "#1F1B17",
  muted: "#94A3B8",
  warmGray: "#64748B",
  border: "#E8E8E6",
  secondary: "#F1F0EE",
  sage: colors.sage,
  coral: "#FF6B6B",
  coralSoft: "#FF8A80",
  coralSurface: "#FFF1F1",
  lavender: colors.lavender,
  butter: colors.butter,
  sky: colors.sky,
  blush: colors.blush,
  mint: colors.mint,
  danger: "#EF4444",
  success: "#10B981",
  overlay: "rgba(15, 23, 42, 0.25)",
  overlayStrong: "rgba(15, 23, 42, 0.4)"
} as const;

export const featureTypography = StyleSheet.create({
  displayLarge: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 40,
    lineHeight: 42,
    color: featurePalette.darkText
  },
  display: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 32,
    lineHeight: 36,
    color: featurePalette.darkText
  },
  title: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 24,
    lineHeight: 28,
    color: featurePalette.darkText
  },
  section: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 20,
    lineHeight: 24,
    color: featurePalette.darkText
  },
  body: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 22,
    color: featurePalette.warmGray
  },
  bodyStrong: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.darkText
  },
  label: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.muted
  },
  microUpper: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  button: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 15,
    lineHeight: 20
  }
});

export const featureShadows = StyleSheet.create({
  sm: {
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2
  },
  md: {
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 4
  },
  lg: {
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.08,
    shadowRadius: 30,
    elevation: 8
  },
  nav: {
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 24,
    elevation: 10
  }
});
