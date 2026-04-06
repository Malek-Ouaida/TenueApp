import type { PropsWithChildren, ReactNode } from "react";
import { StyleSheet, View, type ViewStyle } from "react-native";

import { colors, radius, shadows, spacing } from "../theme";

export type CardTone =
  | "default"
  | "soft"
  | "review"
  | "lookbook"
  | "spotlight"
  | "positive"
  | "organize"
  | "intelligence"
  | "dark";

type CardProps = PropsWithChildren<{
  footer?: ReactNode;
  style?: ViewStyle;
  padded?: boolean;
  tone?: CardTone;
  shadow?: boolean;
}>;

const toneStyles: Record<CardTone, { backgroundColor: string; borderColor: string }> = {
  default: {
    backgroundColor: colors.surface,
    borderColor: colors.border
  },
  soft: {
    backgroundColor: colors.surfaceStrong,
    borderColor: colors.border
  },
  review: {
    backgroundColor: colors.cyanSurface,
    borderColor: "rgba(146, 222, 252, 0.55)"
  },
  lookbook: {
    backgroundColor: colors.melonSurface,
    borderColor: "rgba(248, 184, 179, 0.6)"
  },
  spotlight: {
    backgroundColor: colors.calamansiSurface,
    borderColor: "rgba(247, 253, 175, 0.72)"
  },
  positive: {
    backgroundColor: colors.appleSurface,
    borderColor: "rgba(170, 243, 162, 0.7)"
  },
  organize: {
    backgroundColor: colors.cornflowerSurface,
    borderColor: "rgba(174, 197, 241, 0.62)"
  },
  intelligence: {
    backgroundColor: colors.purpleSurface,
    borderColor: "rgba(177, 167, 240, 0.62)"
  },
  dark: {
    backgroundColor: colors.text,
    borderColor: colors.text
  }
};

export function Card({
  children,
  footer,
  padded = true,
  shadow = true,
  style,
  tone = "default"
}: CardProps) {
  return (
    <View
      style={[
        styles.card,
        padded ? styles.padded : null,
        shadow ? shadows.card : null,
        toneStyles[tone],
        style
      ]}
    >
      {children}
      {footer ? <View style={styles.footer}>{footer}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.lg,
    borderWidth: 1,
    overflow: "hidden"
  },
  padded: {
    padding: spacing.lg
  },
  footer: {
    marginTop: spacing.lg
  }
});
