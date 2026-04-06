export const fontFamilies = {
  sansRegular: "Manrope_500Medium",
  sansSemiBold: "Manrope_600SemiBold",
  sansBold: "Manrope_700Bold",
  serifMedium: "Newsreader_500Medium",
  serifSemiBold: "Newsreader_600SemiBold",
  serifBold: "Newsreader_700Bold"
} as const;

export const textStyles = {
  brand: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 28,
    lineHeight: 30,
    letterSpacing: -1.2
  },
  brandMark: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 22,
    lineHeight: 24,
    letterSpacing: -0.8
  },
  eyebrow: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 2.2,
    textTransform: "uppercase" as const
  },
  micro: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1.4,
    textTransform: "uppercase" as const
  },
  displayLarge: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 50,
    lineHeight: 54
  },
  display: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 42,
    lineHeight: 46
  },
  hero: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 32,
    lineHeight: 38
  },
  title: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 26,
    lineHeight: 32
  },
  sectionTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 22,
    lineHeight: 28
  },
  cardTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 19,
    lineHeight: 24
  },
  body: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 16,
    lineHeight: 25
  },
  bodyStrong: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 16,
    lineHeight: 24
  },
  caption: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
  },
  captionStrong: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18
  },
  button: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 15,
    lineHeight: 20
  },
  tabLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16
  }
} as const;
