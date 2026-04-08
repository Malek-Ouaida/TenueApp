import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { router, type Href } from "expo-router";
import { useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View
} from "react-native";

import { AppText } from "../ui";
import { useAuth } from "../auth/provider";
import { GlassIconButton } from "../ui/feature-components";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";

const SECTIONS = [
  {
    title: "Personal",
    items: [
      { label: "Edit profile", icon: "user", route: "/settings/edit-profile" },
      { label: "Style preferences", icon: "sliders", route: "/settings/preferences" },
      { label: "Saved items", icon: "heart", route: "/settings/wishlist" },
      { label: "Lookbook", icon: "book-open", route: "/lookbook" }
    ]
  },
  {
    title: "App",
    items: [
      { label: "Notifications", icon: "bell", route: "/settings/notifications" },
      { label: "Privacy & media", icon: "shield", route: "/settings/privacy" },
      { label: "Account & security", icon: "lock", route: "/settings/account" }
    ]
  },
  {
    title: "Support",
    items: [{ label: "Help & support", icon: "help-circle", route: "/settings/help" }]
  }
] as const;

export default function SettingsScreen() {
  const { logoutCurrentUser } = useAuth();
  const [showSignOut, setShowSignOut] = useState(false);

  function push(href: string) {
    router.push(href as Href);
  }

  return (
    <ScrollView
      bounces={false}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      style={styles.screen}
    >
      <View style={styles.header}>
        <GlassIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
          onPress={() => router.back()}
        />
      </View>

      <View style={styles.titleBlock}>
        <AppText style={styles.title}>Settings</AppText>
      </View>

      {SECTIONS.map((section) => (
        <View key={section.title} style={styles.section}>
          <AppText style={styles.sectionLabel}>{section.title}</AppText>
          <View style={[styles.card, featureShadows.sm]}>
            {section.items.map((item, index) => (
              <Pressable
                key={item.label}
                onPress={() => push(item.route)}
                style={[
                  styles.row,
                  index < section.items.length - 1 ? styles.rowBorder : null
                ]}
              >
                <Feather color={featurePalette.muted} name={item.icon} size={18} />
                <AppText style={styles.rowLabel}>{item.label}</AppText>
                <Feather color="rgba(100, 116, 139, 0.5)" name="chevron-right" size={16} />
              </Pressable>
            ))}
          </View>
        </View>
      ))}

      <View style={styles.section}>
        {!showSignOut ? (
          <Pressable onPress={() => setShowSignOut(true)} style={[styles.signOutRow, featureShadows.sm]}>
            <MaterialCommunityIcons color={featurePalette.danger} name="logout" size={18} />
            <AppText style={styles.signOutLabel}>Sign out</AppText>
          </Pressable>
        ) : (
          <View style={[styles.confirmCard, featureShadows.sm]}>
            <AppText style={styles.confirmTitle}>Sign out?</AppText>
            <AppText style={styles.confirmCopy}>
              You&apos;ll need to sign in again to access your closet.
            </AppText>
            <View style={styles.confirmActions}>
              <Pressable onPress={() => setShowSignOut(false)} style={styles.confirmSecondary}>
                <AppText style={styles.confirmSecondaryLabel}>Cancel</AppText>
              </Pressable>
              <Pressable
                onPress={() => {
                  void logoutCurrentUser();
                  router.replace("/welcome" as Href);
                }}
                style={styles.confirmPrimary}
              >
                <AppText style={styles.confirmPrimaryLabel}>Sign out</AppText>
              </Pressable>
            </View>
          </View>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  content: {
    paddingTop: 56,
    paddingHorizontal: 20,
    paddingBottom: 32
  },
  header: {
    marginBottom: 12
  },
  titleBlock: {
    paddingHorizontal: 4,
    marginBottom: 24
  },
  title: {
    ...featureTypography.display
  },
  section: {
    marginBottom: 24
  },
  sectionLabel: {
    ...featureTypography.microUpper,
    marginBottom: 8,
    paddingHorizontal: 4
  },
  card: {
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    overflow: "hidden"
  },
  row: {
    height: 56,
    paddingHorizontal: 20,
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  rowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: "rgba(226, 232, 240, 0.6)"
  },
  rowLabel: {
    flex: 1,
    fontFamily: "Manrope_500Medium",
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  signOutRow: {
    height: 56,
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 20
  },
  signOutLabel: {
    fontFamily: "Manrope_500Medium",
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.danger
  },
  confirmCard: {
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    padding: 20
  },
  confirmTitle: {
    ...featureTypography.bodyStrong,
    color: featurePalette.foreground,
    marginBottom: 4
  },
  confirmCopy: {
    ...featureTypography.label,
    marginBottom: 16
  },
  confirmActions: {
    flexDirection: "row",
    gap: 12
  },
  confirmSecondary: {
    flex: 1,
    height: 44,
    borderRadius: 16,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  confirmSecondaryLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  confirmPrimary: {
    flex: 1,
    height: 44,
    borderRadius: 16,
    backgroundColor: featurePalette.danger,
    alignItems: "center",
    justifyContent: "center"
  },
  confirmPrimaryLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 14,
    lineHeight: 18,
    color: "#FFFFFF"
  }
});
