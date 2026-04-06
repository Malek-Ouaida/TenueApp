import type { ReactNode } from "react";
import { StyleSheet, View } from "react-native";

import { colors, spacing } from "../theme";
import { AppText } from "./Typography";

type EmptyStateProps = {
  title: string;
  copy: string;
  action?: ReactNode;
  eyebrow?: string;
};

export function EmptyState({ action, copy, eyebrow, title }: EmptyStateProps) {
  return (
    <View style={styles.root}>
      {eyebrow ? (
        <AppText color={colors.textSubtle} variant="eyebrow">
          {eyebrow}
        </AppText>
      ) : null}
      <AppText variant="title">{title}</AppText>
      <AppText color={colors.textMuted}>{copy}</AppText>
      {action}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    gap: spacing.md,
    paddingVertical: spacing.xl
  }
});
