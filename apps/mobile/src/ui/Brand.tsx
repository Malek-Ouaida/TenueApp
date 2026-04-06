import { StyleSheet, View } from "react-native";

import { colors, radius, spacing } from "../theme";
import { AppText } from "./Typography";

type BrandMarkProps = {
  variant?: "icon" | "wordmark" | "lockup";
  subtle?: boolean;
};

export function BrandMark({
  subtle = false,
  variant = "lockup"
}: BrandMarkProps) {
  if (variant === "wordmark") {
    return (
      <AppText
        variant="brand"
        color={subtle ? colors.textMuted : colors.text}
      >
        tenue.
      </AppText>
    );
  }

  if (variant === "icon") {
    return (
      <View style={[styles.iconShell, subtle ? styles.iconShellSubtle : null]}>
        <AppText variant="brandMark" color={colors.text}>
          t.
        </AppText>
      </View>
    );
  }

  return (
    <View style={styles.lockup}>
      <View style={[styles.iconShell, subtle ? styles.iconShellSubtle : null]}>
        <AppText variant="brandMark" color={colors.text}>
          t.
        </AppText>
      </View>
      <AppText
        variant="brand"
        color={subtle ? colors.textMuted : colors.text}
      >
        tenue.
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  lockup: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm
  },
  iconShell: {
    minWidth: 42,
    height: 42,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  },
  iconShellSubtle: {
    backgroundColor: colors.backgroundSoft
  }
});
