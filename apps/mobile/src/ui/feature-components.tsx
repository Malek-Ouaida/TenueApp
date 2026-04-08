import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { BlurView } from "expo-blur";
import { LinearGradient } from "expo-linear-gradient";
import type { PropsWithChildren, ReactNode } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { fontFamilies } from "../theme";
import { AppText } from "./Typography";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";

export function GlassIconButton({
  icon,
  onPress,
  size = 40
}: {
  icon: ReactNode;
  onPress: () => void;
  size?: number;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.glassIconButton,
        featureShadows.sm,
        { width: size, height: size, borderRadius: size / 2 },
        pressed ? styles.pressed : null
      ]}
    >
      <BlurView intensity={20} style={StyleSheet.absoluteFillObject} tint="light" />
      <View style={styles.glassIconInner}>{icon}</View>
    </Pressable>
  );
}

export function PrimaryActionButton({
  label,
  onPress,
  icon,
  disabled
}: {
  label: string;
  onPress: () => void;
  icon?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.primaryButton,
        featureShadows.lg,
        disabled ? styles.disabled : null,
        pressed && !disabled ? styles.pressedWide : null
      ]}
    >
      <View style={styles.primaryButtonContent}>
        {icon}
        <AppText style={styles.primaryButtonLabel}>{label}</AppText>
      </View>
    </Pressable>
  );
}

export function SecondaryActionButton({
  label,
  onPress,
  icon
}: {
  label: string;
  onPress: () => void;
  icon?: ReactNode;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.secondaryButton, pressed ? styles.pressedWide : null]}
    >
      <View style={styles.primaryButtonContent}>
        {icon}
        <AppText style={styles.secondaryButtonLabel}>{label}</AppText>
      </View>
    </Pressable>
  );
}

export function SectionEyebrow({ children }: PropsWithChildren) {
  return <AppText style={featureTypography.microUpper}>{children}</AppText>;
}

export function FeatureSheet({
  children,
  footer,
  onClose,
  title,
  visible
}: PropsWithChildren<{
  footer?: ReactNode;
  onClose: () => void;
  title?: string;
  visible: boolean;
}>) {
  const insets = useSafeAreaInsets();

  return (
    <Modal animationType="none" onRequestClose={onClose} transparent visible={visible}>
      <Pressable onPress={onClose} style={StyleSheet.absoluteFillObject}>
        <BlurView intensity={18} style={StyleSheet.absoluteFillObject} tint="light" />
        <View style={styles.sheetOverlay} />
      </Pressable>
      <View style={[styles.sheet, { paddingBottom: insets.bottom + 24 }]}>
        <View style={styles.sheetHandle} />
        {title ? <AppText style={styles.sheetTitle}>{title}</AppText> : null}
        <ScrollView
          bounces={false}
          contentContainerStyle={styles.sheetScroll}
          showsVerticalScrollIndicator={false}
        >
          {children}
        </ScrollView>
        {footer ? <View style={styles.sheetFooter}>{footer}</View> : null}
      </View>
    </Modal>
  );
}

export function FtueOverlay({
  onDismiss,
  onNext,
  step,
  total,
  title,
  description
}: {
  onDismiss: () => void;
  onNext: () => void;
  step: number;
  total: number;
  title: string;
  description: string;
}) {
  return (
    <Modal animationType="fade" onRequestClose={onDismiss} transparent visible>
      <View style={styles.ftueRoot}>
        <BlurView intensity={14} style={StyleSheet.absoluteFillObject} tint="light" />
        <View style={styles.ftueCard}>
          <Pressable onPress={onDismiss} style={styles.ftueClose}>
            <Feather color={featurePalette.muted} name="x" size={16} />
          </Pressable>

          <View style={styles.ftueIconShell}>
            {step === 0 ? (
              <MaterialCommunityIcons
                color={featurePalette.coral}
                name="hanger"
                size={26}
              />
            ) : (
              <Feather color={featurePalette.coral} name="camera" size={24} />
            )}
          </View>

          <AppText style={styles.ftueTitle}>{title}</AppText>
          <AppText style={styles.ftueDescription}>{description}</AppText>

          <View style={styles.ftueFooter}>
            <View style={styles.ftueDots}>
              {Array.from({ length: total }).map((_, index) => (
                <View
                  key={index}
                  style={[
                    styles.ftueDot,
                    index === step ? styles.ftueDotActive : null
                  ]}
                />
              ))}
            </View>

            <Pressable onPress={onNext} style={({ pressed }) => [styles.ftueCta, pressed ? styles.pressedWide : null]}>
              <LinearGradient
                colors={[featurePalette.coral, featurePalette.coralSoft]}
                end={{ x: 1, y: 1 }}
                start={{ x: 0, y: 0 }}
                style={styles.ftueCtaGradient}
              >
                <AppText style={styles.ftueCtaLabel}>{step < total - 1 ? "Next" : "Got it"}</AppText>
              </LinearGradient>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

export function EmptyPhotoState({
  label,
  onPress,
  subtitle
}: {
  label: string;
  onPress: () => void;
  subtitle: string;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.emptyPhotoState, featureShadows.sm, pressed ? styles.pressedWide : null]}>
      <View style={styles.emptyPhotoIcon}>
        <Feather color={featurePalette.muted} name="camera" size={22} />
      </View>
      <AppText style={styles.emptyPhotoTitle}>{label}</AppText>
      <AppText style={styles.emptyPhotoSubtitle}>{subtitle}</AppText>
    </Pressable>
  );
}

export function FeatureTextArea({
  placeholder,
  value,
  onChangeText
}: {
  placeholder: string;
  value: string;
  onChangeText: (value: string) => void;
}) {
  return (
    <TextInput
      multiline
      onChangeText={onChangeText}
      placeholder={placeholder}
      placeholderTextColor={featurePalette.muted}
      style={styles.textArea}
      textAlignVertical="top"
      value={value}
    />
  );
}

const styles = StyleSheet.create({
  pressed: {
    transform: [{ scale: 0.95 }]
  },
  pressedWide: {
    transform: [{ scale: 0.97 }]
  },
  glassIconButton: {
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.85)",
    alignItems: "center",
    justifyContent: "center"
  },
  glassIconInner: {
    alignItems: "center",
    justifyContent: "center"
  },
  primaryButton: {
    height: 52,
    borderRadius: 26,
    overflow: "hidden",
    backgroundColor: featurePalette.darkText,
    alignItems: "center",
    justifyContent: "center"
  },
  primaryButtonContent: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  primaryButtonLabel: {
    ...featureTypography.button,
    color: "#FFFFFF"
  },
  secondaryButton: {
    height: 52,
    borderRadius: 26,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  secondaryButtonLabel: {
    ...featureTypography.button,
    color: featurePalette.darkText
  },
  disabled: {
    opacity: 0.4
  },
  sheetOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: featurePalette.overlay
  },
  sheet: {
    marginTop: "auto",
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingTop: 12,
    paddingHorizontal: 24,
    maxHeight: "78%"
  },
  sheetHandle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 999,
    backgroundColor: "#E2E8F0",
    marginBottom: 12
  },
  sheetTitle: {
    ...featureTypography.title,
    fontSize: 20,
    marginBottom: 12
  },
  sheetScroll: {
    gap: 12,
    paddingBottom: 8
  },
  sheetFooter: {
    paddingTop: 16,
    gap: 12
  },
  ftueRoot: {
    flex: 1,
    justifyContent: "flex-end",
    paddingHorizontal: 16,
    paddingBottom: 32,
    backgroundColor: featurePalette.overlayStrong
  },
  ftueCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    padding: 24,
    ...featureShadows.lg
  },
  ftueClose: {
    position: "absolute",
    top: 16,
    right: 16,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#F8F8F6",
    alignItems: "center",
    justifyContent: "center"
  },
  ftueIconShell: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: featurePalette.coralSurface,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16
  },
  ftueTitle: {
    ...featureTypography.section,
    letterSpacing: -0.4,
    marginBottom: 6
  },
  ftueDescription: {
    ...featureTypography.body,
    marginBottom: 24
  },
  ftueFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12
  },
  ftueDots: {
    flexDirection: "row",
    gap: 6
  },
  ftueDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#E8E8E6"
  },
  ftueDotActive: {
    width: 20,
    backgroundColor: featurePalette.coral
  },
  ftueCta: {
    borderRadius: 22,
    overflow: "hidden"
  },
  ftueCtaGradient: {
    minHeight: 44,
    paddingHorizontal: 24,
    alignItems: "center",
    justifyContent: "center"
  },
  ftueCtaLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 14,
    lineHeight: 18,
    color: "#FFFFFF"
  },
  emptyPhotoState: {
    width: "100%",
    aspectRatio: 4 / 3,
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  emptyPhotoIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  emptyPhotoTitle: {
    ...featureTypography.bodyStrong
  },
  emptyPhotoSubtitle: {
    ...featureTypography.label
  },
  textArea: {
    minHeight: 88,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 20,
    color: featurePalette.darkText
  }
});
