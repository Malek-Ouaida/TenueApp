import { Feather } from "@expo/vector-icons";
import { StatusBar } from "expo-status-bar";
import { LinearGradient } from "expo-linear-gradient";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Animated,
  Easing,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type TextStyle,
  type ViewStyle
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { colors, fontFamilies } from "../theme";
import { AppText } from "../ui";

export const authPalette = {
  background: "#FAF9F7",
  surface: "#FFFFFF",
  text: colors.darkText,
  muted: "#94A3B8",
  subtle: "#CBD5E1",
  border: "#F1F0EE",
  accent: "#FF6B6B",
  accentSoft: "#FF8A80",
  accentSurface: "#FFF5F3",
  accentSurfaceStrong: "#FFEAE4",
  accentLine: "#FFDDD2",
  accentShadow: "rgba(255, 107, 107, 0.24)",
  shadow: "rgba(15, 23, 42, 0.08)"
} as const;

type AuthScreenProps = {
  children: ReactNode;
  footer?: ReactNode;
  scrollable?: boolean;
  contentStyle?: StyleProp<ViewStyle>;
  backgroundDecor?: ReactNode;
};

type AuthTextFieldProps = Omit<TextInputProps, "style"> & {
  label: string;
  helper?: string | null;
  error?: string | null;
  leftIcon?: ReactNode;
  rightAccessory?: ReactNode;
  style?: StyleProp<TextStyle>;
  containerStyle?: StyleProp<ViewStyle>;
};

type AuthPrimaryButtonProps = {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
};

export function AuthScreen({
  backgroundDecor,
  children,
  contentStyle,
  footer,
  scrollable = true
}: AuthScreenProps) {
  const insets = useSafeAreaInsets();
  const content = (
    <View
      style={[
        styles.screenContent,
        footer ? styles.screenContentWithFooter : null,
        contentStyle
      ]}
    >
      {children}
    </View>
  );

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "left", "right"]}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.page}
      >
        {backgroundDecor ? (
          <View pointerEvents="none" style={styles.backgroundDecor}>
            {backgroundDecor}
          </View>
        ) : null}
        {scrollable ? (
          <ScrollView
            bounces={false}
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
            style={styles.flex}
          >
            {content}
          </ScrollView>
        ) : (
          content
        )}
        {footer ? (
          <View
            style={[
              styles.footer,
              {
                paddingBottom: Math.max(insets.bottom + 10, 24)
              }
            ]}
          >
            {footer}
          </View>
        ) : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function AuthBackButton({
  onPress,
  variant = "subtle"
}: {
  onPress: () => void;
  variant?: "subtle" | "surface";
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.backButton,
        variant === "surface" ? styles.backButtonSurface : styles.backButtonSubtle,
        pressed ? styles.pressed : null
      ]}
    >
      <Feather color={authPalette.text} name="arrow-left" size={18} />
    </Pressable>
  );
}

export function AuthTextField({
  containerStyle,
  error,
  helper,
  label,
  leftIcon,
  onBlur,
  onFocus,
  rightAccessory,
  style,
  ...props
}: AuthTextFieldProps) {
  const [focused, setFocused] = useState(false);
  const labelColor = error
    ? colors.danger
    : focused
      ? authPalette.accent
      : authPalette.muted;
  const borderColor = error
    ? colors.danger
    : focused
      ? authPalette.accent
      : authPalette.border;

  function handleFocus(event: Parameters<NonNullable<TextInputProps["onFocus"]>>[0]) {
    setFocused(true);
    onFocus?.(event);
  }

  function handleBlur(event: Parameters<NonNullable<TextInputProps["onBlur"]>>[0]) {
    setFocused(false);
    onBlur?.(event);
  }

  return (
    <View style={[styles.fieldRoot, containerStyle]}>
      <AppText style={[styles.fieldLabel, { color: labelColor }]}>{label}</AppText>
      <View
        style={[
          styles.inputShell,
          { borderColor },
          focused ? styles.inputShellFocused : null
        ]}
      >
        {leftIcon ? <View style={styles.leadingAccessory}>{leftIcon}</View> : null}
        <TextInput
          {...props}
          onBlur={handleBlur}
          onFocus={handleFocus}
          placeholderTextColor={authPalette.subtle}
          style={[
            styles.input,
            leftIcon ? styles.inputWithLeadingAccessory : null,
            rightAccessory ? styles.inputWithTrailingAccessory : null,
            props.multiline ? styles.multilineInput : null,
            style
          ]}
        />
        {rightAccessory ? <View style={styles.trailingAccessory}>{rightAccessory}</View> : null}
      </View>
      {error ? (
        <AppText color={colors.danger} style={styles.messageText}>
          {error}
        </AppText>
      ) : helper ? (
        <AppText color={authPalette.subtle} style={styles.messageText}>
          {helper}
        </AppText>
      ) : null}
    </View>
  );
}

export function AuthPrimaryButton({
  disabled = false,
  label,
  loading = false,
  onPress,
  style
}: AuthPrimaryButtonProps) {
  return (
    <Pressable
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.buttonPressable,
        style,
        pressed && !disabled && !loading ? styles.pressed : null
      ]}
    >
      <LinearGradient
        colors={
          disabled
            ? [authPalette.border, authPalette.border]
            : [authPalette.accent, authPalette.accentSoft]
        }
        end={{ x: 1, y: 1 }}
        start={{ x: 0, y: 0 }}
        style={[styles.primaryButton, disabled ? styles.primaryButtonDisabled : null]}
      >
        {loading ? (
          <ActivityIndicator color={disabled ? authPalette.subtle : colors.white} />
        ) : (
          <AppText color={disabled ? authPalette.subtle : colors.white} style={styles.buttonLabel}>
            {label}
          </AppText>
        )}
      </LinearGradient>
    </Pressable>
  );
}

export function AuthFooterLink({
  label,
  onPress,
  prefix
}: {
  label: string;
  onPress: () => void;
  prefix: string;
}) {
  return (
    <View style={styles.footerLinkRow}>
      <AppText color={authPalette.muted} style={styles.footerLinkText}>
        {prefix}
      </AppText>
      <Pressable onPress={onPress} style={({ pressed }) => [pressed ? styles.pressed : null]}>
        <AppText color={authPalette.text} style={[styles.footerLinkText, styles.footerLinkTextStrong]}>
          {label}
        </AppText>
      </Pressable>
    </View>
  );
}

export function useAuthIntroAnimation(count: number) {
  const values = useRef(Array.from({ length: count }, () => new Animated.Value(0))).current;

  useEffect(() => {
    const timer = setTimeout(() => {
      Animated.stagger(
        90,
        values.map((value) =>
          Animated.timing(value, {
            toValue: 1,
            duration: 560,
            easing: Easing.bezier(0.32, 0.72, 0, 1),
            useNativeDriver: true
          })
        )
      ).start();
    }, 40);

    return () => {
      clearTimeout(timer);
    };
  }, [values]);

  return values;
}

export function buildFadeUpStyle(value: Animated.Value, offset = 16) {
  return {
    opacity: value,
    transform: [
      {
        translateY: value.interpolate({
          inputRange: [0, 1],
          outputRange: [offset, 0]
        })
      }
    ]
  };
}

export function buildScaleInStyle(
  value: Animated.Value,
  options?: {
    fromScale?: number;
    fromTranslateY?: number;
  }
) {
  const fromScale = options?.fromScale ?? 0.85;
  const fromTranslateY = options?.fromTranslateY ?? 12;

  return {
    opacity: value,
    transform: [
      {
        scale: value.interpolate({
          inputRange: [0, 1],
          outputRange: [fromScale, 1]
        })
      },
      {
        translateY: value.interpolate({
          inputRange: [0, 1],
          outputRange: [fromTranslateY, 0]
        })
      }
    ]
  };
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: authPalette.background
  },
  page: {
    flex: 1,
    backgroundColor: authPalette.background
  },
  flex: {
    flex: 1
  },
  backgroundDecor: {
    ...StyleSheet.absoluteFillObject
  },
  scrollContent: {
    flexGrow: 1
  },
  screenContent: {
    flexGrow: 1,
    paddingHorizontal: 28,
    paddingTop: 14,
    paddingBottom: 32
  },
  screenContentWithFooter: {
    paddingBottom: 160
  },
  footer: {
    paddingHorizontal: 28,
    paddingTop: 16,
    backgroundColor: authPalette.background
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center"
  },
  backButtonSubtle: {
    backgroundColor: "rgba(0, 0, 0, 0.04)"
  },
  backButtonSurface: {
    backgroundColor: authPalette.surface,
    shadowColor: "rgba(0, 0, 0, 0.08)",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 8,
    elevation: 3
  },
  fieldRoot: {
    gap: 10
  },
  fieldLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1,
    textTransform: "uppercase"
  },
  inputShell: {
    minHeight: 52,
    borderRadius: 16,
    borderWidth: 2,
    backgroundColor: authPalette.surface,
    flexDirection: "row",
    alignItems: "center"
  },
  inputShellFocused: {
    shadowColor: authPalette.accent,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 2
  },
  leadingAccessory: {
    paddingLeft: 16
  },
  trailingAccessory: {
    paddingRight: 16
  },
  input: {
    flex: 1,
    minHeight: 52,
    paddingHorizontal: 20,
    color: authPalette.text,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15
  },
  inputWithLeadingAccessory: {
    paddingLeft: 12
  },
  inputWithTrailingAccessory: {
    paddingRight: 12
  },
  multilineInput: {
    minHeight: 96,
    paddingTop: 14,
    paddingBottom: 14,
    textAlignVertical: "top"
  },
  messageText: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 18
  },
  buttonPressable: {
    borderRadius: 28
  },
  primaryButton: {
    minHeight: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: authPalette.accent,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.3,
    shadowRadius: 20,
    elevation: 8
  },
  primaryButtonDisabled: {
    shadowOpacity: 0,
    elevation: 0
  },
  buttonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15,
    lineHeight: 20,
    letterSpacing: -0.15
  },
  footerLinkRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    marginTop: 14
  },
  footerLinkText: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
  },
  footerLinkTextStrong: {
    fontFamily: fontFamilies.sansSemiBold
  },
  pressed: {
    opacity: 0.72,
    transform: [{ scale: 0.98 }]
  }
});
