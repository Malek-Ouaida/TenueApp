import { ActivityIndicator, Pressable, StyleSheet, View, type TextStyle, type ViewStyle } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import type { ReactNode } from "react";

import { colors, radius, spacing } from "../theme";
import { AppText } from "./Typography";

type ButtonProps = {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: "primary" | "secondary" | "ghost";
  tone?: "dark" | "review" | "intelligence" | "positive" | "organize";
  icon?: ReactNode;
  size?: "sm" | "md" | "lg";
  style?: ViewStyle;
  textStyle?: TextStyle;
};

export function Button({
  disabled = false,
  icon,
  label,
  loading = false,
  onPress,
  size = "md",
  style,
  textStyle,
  tone = "dark",
  variant = "primary"
}: ButtonProps) {
  const primaryColors =
    tone === "review"
      ? ([colors.cyan, "#62C7EF"] as const)
      : tone === "intelligence"
        ? ([colors.purple, "#8F84E4"] as const)
        : tone === "positive"
          ? ([colors.apple, "#82DA7B"] as const)
          : tone === "organize"
            ? ([colors.cornflower, "#88A7E8"] as const)
            : ([colors.text, "#2d2824"] as const);

  const content = (
    <View style={styles.content}>
      {loading ? (
        <ActivityIndicator color={variant === "primary" ? colors.white : colors.text} />
      ) : (
        <>
          {icon}
          <AppText
            variant="button"
            color={variant === "primary" ? colors.white : colors.text}
            style={textStyle}
          >
            {label}
          </AppText>
        </>
      )}
    </View>
  );

  if (variant === "primary") {
    return (
      <Pressable
        disabled={disabled || loading}
        onPress={onPress}
        style={[styles.pressable, style]}
      >
        <LinearGradient
          colors={primaryColors}
          end={{ x: 1, y: 1 }}
          start={{ x: 0, y: 0 }}
          style={[
            styles.base,
            sizeStyles[size],
            styles.primary,
            disabled ? styles.disabled : null
          ]}
        >
          {content}
        </LinearGradient>
      </Pressable>
    );
  }

  return (
    <Pressable
      disabled={disabled || loading}
      onPress={onPress}
      style={[
        styles.base,
        sizeStyles[size],
        variant === "secondary" ? styles.secondary : styles.ghost,
        style,
        disabled ? styles.disabled : null
      ]}
    >
      {content}
    </Pressable>
  );
}

const sizeStyles = StyleSheet.create({
  sm: {
    minHeight: 42,
    paddingHorizontal: spacing.md
  },
  md: {
    minHeight: 54,
    paddingHorizontal: spacing.lg
  },
  lg: {
    minHeight: 60,
    paddingHorizontal: spacing.xl
  }
});

const styles = StyleSheet.create({
  pressable: {
    borderRadius: radius.md
  },
  base: {
    borderRadius: radius.md,
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden"
  },
  primary: {
    borderWidth: 1,
    borderColor: "rgba(23, 20, 17, 0.06)"
  },
  secondary: {
    backgroundColor: colors.surfaceStrong,
    borderWidth: 1,
    borderColor: colors.border
  },
  ghost: {
    backgroundColor: "rgba(255, 255, 255, 0.001)"
  },
  disabled: {
    opacity: 0.5
  },
  content: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm
  }
});
