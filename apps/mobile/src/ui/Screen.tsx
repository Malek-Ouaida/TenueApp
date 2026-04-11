import { StatusBar } from "expo-status-bar";
import type { PropsWithChildren, ReactNode } from "react";
import { ScrollView, StyleSheet, View, type ScrollViewProps, type ViewStyle } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { colors, spacing } from "../theme";

type ScreenProps = PropsWithChildren<{
  backgroundColor?: string;
  padded?: boolean;
  scrollable?: boolean;
  footer?: ReactNode;
  contentContainerStyle?: ScrollViewProps["contentContainerStyle"];
  style?: ViewStyle;
}>;

export function Screen({
  backgroundColor = colors.background,
  children,
  contentContainerStyle,
  footer,
  padded = true,
  scrollable = true,
  style
}: ScreenProps) {
  const insets = useSafeAreaInsets();

  const inner = (
    <View
      style={[
        styles.content,
        padded ? styles.padded : null,
        footer ? { paddingBottom: spacing.xxxl + insets.bottom } : null,
        style
      ]}
    >
      {children}
    </View>
  );

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor }]} edges={["top", "left", "right"]}>
      <StatusBar style="dark" />
      {scrollable ? (
        <ScrollView
          keyboardDismissMode="interactive"
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          style={styles.scroll}
          contentContainerStyle={[styles.scrollContent, contentContainerStyle]}
        >
          {inner}
        </ScrollView>
      ) : (
        inner
      )}
      {footer ? <View style={[styles.footer, { paddingBottom: spacing.md + insets.bottom }]}>{footer}</View> : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1
  },
  scroll: {
    flex: 1
  },
  scrollContent: {
    flexGrow: 1
  },
  content: {
    flexGrow: 1
  },
  padded: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    gap: spacing.lg
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    backgroundColor: "rgba(246, 242, 235, 0.94)"
  }
});
