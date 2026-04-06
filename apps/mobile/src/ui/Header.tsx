import type { ReactNode } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { colors, spacing } from "../theme";
import { AppText } from "./Typography";

type HeaderProps = {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  leading?: ReactNode;
  trailing?: ReactNode;
};

export function Header({ eyebrow, leading, subtitle, title, trailing }: HeaderProps) {
  return (
    <View style={styles.root}>
      <View style={styles.row}>
        <View style={styles.leading}>{leading}</View>
        <View style={styles.copy}>
          {eyebrow ? (
            <AppText variant="eyebrow" color={colors.textSubtle}>
              {eyebrow}
            </AppText>
          ) : null}
          <AppText variant="hero">{title}</AppText>
          {subtitle ? (
            <AppText color={colors.textMuted}>{subtitle}</AppText>
          ) : null}
        </View>
        <View style={styles.trailing}>{trailing}</View>
      </View>
    </View>
  );
}

type HeaderActionProps = {
  label: string;
  onPress: () => void;
};

export function HeaderAction({ label, onPress }: HeaderActionProps) {
  return (
    <Pressable onPress={onPress} style={styles.action}>
      <AppText variant="caption" color={colors.text}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    gap: spacing.sm
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.md
  },
  leading: {
    minWidth: 40,
    alignItems: "flex-start"
  },
  trailing: {
    minWidth: 40,
    alignItems: "flex-end",
    marginLeft: "auto"
  },
  copy: {
    flex: 1,
    gap: spacing.xs
  },
  action: {
    minHeight: 38,
    minWidth: 38,
    paddingHorizontal: spacing.sm,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  }
});
