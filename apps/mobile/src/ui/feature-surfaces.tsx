import { BlurView } from "expo-blur";
import { LinearGradient } from "expo-linear-gradient";
import { Image } from "expo-image";
import type { ReactNode } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { fontFamilies } from "../theme";
import { AppText } from "./Typography";
import { featurePalette, featureShadows } from "../theme/feature";

export function FeatureScreen({
  children,
  contentContainerStyle,
  style
}: {
  children: ReactNode;
  contentContainerStyle?: object;
  style?: object;
}) {
  return (
    <ScrollView
      bounces={false}
      contentContainerStyle={[styles.screenContent, contentContainerStyle]}
      showsVerticalScrollIndicator={false}
      style={[styles.screen, style]}
    >
      {children}
    </ScrollView>
  );
}

export function SurfaceIconButton({
  icon,
  onPress,
  translucent
}: {
  icon: ReactNode;
  onPress: () => void;
  translucent?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.iconButton,
        translucent ? styles.iconButtonTranslucent : styles.iconButtonSolid,
        pressed ? styles.pressed : null
      ]}
    >
      {translucent ? (
        <BlurView intensity={18} style={StyleSheet.absoluteFillObject} tint="light" />
      ) : null}
      <View style={styles.iconButtonInner}>{icon}</View>
    </Pressable>
  );
}

export function FeatureChip({
  active,
  label,
  onPress
}: {
  active: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        active ? styles.chipActive : styles.chipIdle,
        !active ? featureShadows.sm : null,
        pressed ? styles.pressed : null
      ]}
    >
      <AppText style={[styles.chipLabel, active ? styles.chipLabelActive : null]}>{label}</AppText>
    </Pressable>
  );
}

export { FeatureChip as Chip };

export function StickyActionBar({ children }: { children: ReactNode }) {
  return (
    <View style={styles.stickyBarShell}>
      <BlurView intensity={24} style={StyleSheet.absoluteFillObject} tint="light" />
      <View style={styles.stickyBar}>{children}</View>
    </View>
  );
}

export function LoadingState({
  backgroundUri,
  icon,
  subtitle,
  title,
  variant = "light"
}: {
  backgroundUri?: string | null;
  icon: ReactNode;
  subtitle: string;
  title: string;
  variant?: "dark" | "light";
}) {
  const dark = variant === "dark";

  return (
    <View style={[styles.loadingScreen, dark ? styles.loadingScreenDark : null]}>
      {backgroundUri ? (
        <Image contentFit="cover" source={{ uri: backgroundUri }} style={StyleSheet.absoluteFillObject} />
      ) : null}
      {backgroundUri ? (
        <View
          style={[
            StyleSheet.absoluteFillObject,
            {
              backgroundColor: dark ? "rgba(15, 23, 42, 0.52)" : "rgba(250, 249, 247, 0.72)"
            }
          ]}
        />
      ) : null}
      <View style={[styles.loadingOrb, dark ? styles.loadingOrbDark : null]}>
        {icon}
        <LinearGradient
          colors={[
            "transparent",
            dark ? "rgba(255,255,255,0.28)" : "rgba(232, 219, 255, 0.4)",
            "transparent"
          ]}
          end={{ x: 1, y: 0.5 }}
          start={{ x: 0, y: 0.5 }}
          style={styles.loadingShimmer}
        />
      </View>
      <AppText style={[styles.loadingTitle, dark ? styles.loadingTitleDark : null]}>{title}</AppText>
      <AppText style={[styles.loadingSubtitle, dark ? styles.loadingSubtitleDark : null]}>
        {subtitle}
      </AppText>
    </View>
  );
}

export function SectionHeading({
  title,
  subtitle
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <View style={styles.headingBlock}>
      <AppText style={styles.headingTitle}>{title}</AppText>
      {subtitle ? <AppText style={styles.headingSubtitle}>{subtitle}</AppText> : null}
    </View>
  );
}

export function FeatureSwitch({
  onToggle,
  value
}: {
  onToggle: () => void;
  value: boolean;
}) {
  return (
    <Pressable
      onPress={onToggle}
      style={[styles.switchRoot, value ? styles.switchRootActive : styles.switchRootIdle]}
    >
      <View style={[styles.switchThumb, value ? styles.switchThumbActive : styles.switchThumbIdle]} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  screenContent: {
    paddingTop: 56,
    paddingHorizontal: 24,
    paddingBottom: 36
  },
  pressed: {
    opacity: 0.9,
    transform: [{ scale: 0.97 }]
  },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center"
  },
  iconButtonSolid: {
    backgroundColor: "rgba(255,255,255,0.92)",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 12,
    elevation: 2
  },
  iconButtonTranslucent: {
    backgroundColor: "rgba(255,255,255,0.72)"
  },
  iconButtonInner: {
    alignItems: "center",
    justifyContent: "center"
  },
  chip: {
    minHeight: 38,
    paddingHorizontal: 16,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center"
  },
  chipIdle: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: featurePalette.border
  },
  chipActive: {
    backgroundColor: featurePalette.foreground
  },
  chipLabel: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  chipLabelActive: {
    color: "#FFFFFF"
  },
  stickyBarShell: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    overflow: "hidden"
  },
  stickyBar: {
    paddingHorizontal: 24,
    paddingTop: 18,
    paddingBottom: 32,
    gap: 12
  },
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
    backgroundColor: featurePalette.background
  },
  loadingScreenDark: {
    backgroundColor: featurePalette.foreground
  },
  loadingOrb: {
    width: 80,
    height: 80,
    borderRadius: 40,
    marginBottom: 32,
    overflow: "hidden",
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 32,
    elevation: 8
  },
  loadingOrbDark: {
    backgroundColor: "rgba(255,255,255,0.1)"
  },
  loadingShimmer: {
    ...StyleSheet.absoluteFillObject,
    transform: [{ translateX: 100 }]
  },
  loadingTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 24,
    lineHeight: 30,
    letterSpacing: -0.36,
    color: featurePalette.foreground,
    textAlign: "center"
  },
  loadingTitleDark: {
    color: "#FFFFFF"
  },
  loadingSubtitle: {
    marginTop: 8,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 22,
    color: featurePalette.muted,
    textAlign: "center"
  },
  loadingSubtitleDark: {
    color: "rgba(255,255,255,0.68)"
  },
  headingBlock: {
    marginBottom: 12
  },
  headingTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 26,
    lineHeight: 32,
    letterSpacing: -0.52,
    color: featurePalette.foreground
  },
  headingSubtitle: {
    marginTop: 6,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 20,
    color: featurePalette.muted
  },
  switchRoot: {
    width: 44,
    height: 26,
    borderRadius: 13,
    justifyContent: "center"
  },
  switchRootIdle: {
    backgroundColor: featurePalette.secondary
  },
  switchRootActive: {
    backgroundColor: featurePalette.foreground
  },
  switchThumb: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: "#FFFFFF"
  },
  switchThumbIdle: {
    marginLeft: 3
  },
  switchThumbActive: {
    marginLeft: 21
  }
});
