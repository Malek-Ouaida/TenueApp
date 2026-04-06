import { StyleSheet, View } from "react-native";

import { colors, radius, spacing } from "../theme";
import { AppText } from "./Typography";

export type ChipTone =
  | "default"
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "muted"
  | "review"
  | "lookbook"
  | "spotlight"
  | "positive"
  | "organize"
  | "intelligence"
  | "dark";

type ChipProps = {
  label: string;
  tone?: ChipTone;
};

const toneStyles: Record<ChipTone, { backgroundColor: string; color: string }> = {
  default: {
    backgroundColor: colors.surfaceStrong,
    color: colors.text
  },
  accent: {
    backgroundColor: colors.accentSoft,
    color: colors.text
  },
  success: {
    backgroundColor: "rgba(77, 122, 81, 0.16)",
    color: colors.success
  },
  warning: {
    backgroundColor: "rgba(154, 106, 52, 0.16)",
    color: colors.warning
  },
  danger: {
    backgroundColor: "rgba(176, 82, 70, 0.12)",
    color: colors.danger
  },
  muted: {
    backgroundColor: "rgba(23, 20, 17, 0.06)",
    color: colors.textMuted
  },
  review: {
    backgroundColor: colors.cyanSurface,
    color: colors.text
  },
  lookbook: {
    backgroundColor: colors.melonSurface,
    color: colors.text
  },
  spotlight: {
    backgroundColor: colors.calamansiSurface,
    color: colors.text
  },
  positive: {
    backgroundColor: colors.appleSurface,
    color: colors.text
  },
  organize: {
    backgroundColor: colors.cornflowerSurface,
    color: colors.text
  },
  intelligence: {
    backgroundColor: colors.purpleSurface,
    color: colors.text
  },
  dark: {
    backgroundColor: colors.text,
    color: colors.white
  }
};

export function Chip({ label, tone = "default" }: ChipProps) {
  return (
    <View style={[styles.container, { backgroundColor: toneStyles[tone].backgroundColor }]}>
      <AppText color={toneStyles[tone].color} variant="captionStrong">
        {label}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignSelf: "flex-start",
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 8
  }
});
