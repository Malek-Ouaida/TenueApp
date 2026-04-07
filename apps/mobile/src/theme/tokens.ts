export const colors = {
  background: "#f6f2eb",
  backgroundMuted: "#ede7dd",
  backgroundSoft: "#fbf8f3",
  cream: "#FAF9F7",
  warmWhite: "#FFFFFF",
  surface: "rgba(255, 252, 247, 0.96)",
  surfaceStrong: "#fffdfa",
  surfaceElevated: "#ffffff",
  surfaceOverlay: "rgba(26, 23, 20, 0.16)",
  text: "#171411",
  darkText: "#0F172A",
  textMuted: "#615850",
  warmGray: "#867D74",
  textSubtle: "#8a8076",
  border: "rgba(24, 20, 17, 0.08)",
  borderStrong: "rgba(24, 20, 17, 0.14)",
  accent: "#191613",
  accentSoft: "#efebe4",
  success: "#4d7a51",
  warning: "#9a6a34",
  danger: "#b05246",
  shadow: "rgba(21, 18, 15, 0.08)",
  sage: "#D8EBCF",
  coral: "#FFD2C2",
  lavender: "#E8DBFF",
  butter: "#FFEFA1",
  sky: "#DCEAF7",
  blush: "#FFEAF2",
  mint: "#DDF1E7",
  melon: "#F8B8B3",
  calamansi: "#F7FDAF",
  apple: "#AAF3A2",
  cyan: "#92DEFC",
  cornflower: "#AEC5F1",
  purple: "#B1A7F0",
  melonSurface: "#FCE8E5",
  calamansiSurface: "#FBFDDC",
  appleSurface: "#E8FBE4",
  cyanSurface: "#E3F6FE",
  cornflowerSurface: "#E5ECFB",
  purpleSurface: "#ECE9FC",
  white: "#ffffff",
  black: "#000000"
} as const;

export const spacing = {
  xs: 6,
  sm: 10,
  md: 16,
  lg: 20,
  xl: 28,
  xxl: 40,
  xxxl: 52
} as const;

export const radius = {
  sm: 16,
  md: 24,
  lg: 32,
  xl: 40,
  pill: 999
} as const;

export const shadows = {
  card: {
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 1,
    shadowRadius: 32,
    elevation: 12
  },
  soft: {
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 1,
    shadowRadius: 18,
    elevation: 4
  }
} as const;
