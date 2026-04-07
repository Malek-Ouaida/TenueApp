import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useMemo, useState, type ReactNode } from "react";
import { Modal, Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, spacing } from "../theme";
import { AppText } from "./Typography";

const palette = {
  cream: colors.cream,
  warmWhite: colors.warmWhite,
  darkText: colors.darkText,
  warmGray: "#867D74",
  coral: "#FF6B6B",
  sage: "#D8EBCF",
  sky: "#DCEAF7",
  butter: "#FFEFA1",
  lavender: "#E8DBFF",
  blush: "#FFEAF2",
  overlay: "rgba(15, 23, 42, 0.25)"
} as const;

type TabKey = "home" | "closet" | "add" | "style" | "profile";

type TenueTabBarProps = {
  descriptors: Record<string, { options: { title?: string } }>;
  navigation: {
    navigate: (name: string) => void;
  };
  state: {
    index: number;
    routes: Array<{ key: string; name: string }>;
  };
};

export function TenueTabBar({ navigation, state }: TenueTabBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  const routeMap = useMemo(() => {
    const nextMap = new Map<TabKey, string>();

    state.routes.forEach((route) => {
      const normalized = normalizeRouteName(route.name);
      if (normalized) {
        nextMap.set(normalized, route.name);
      }
    });

    return nextMap;
  }, [state.routes]);

  const focused = normalizeRouteName(state.routes[state.index]?.name);

  function navigateTo(target: TabKey) {
    const routeName = routeMap.get(target);
    if (!routeName) {
      return;
    }

    setMenuOpen(false);
    void Haptics.selectionAsync();
    navigation.navigate(routeName);
  }

  return (
    <>
      <Modal animationType="fade" transparent visible={menuOpen}>
        <View style={styles.modalOverlay}>
          <Pressable onPress={() => setMenuOpen(false)} style={StyleSheet.absoluteFillObject} />
          <View style={styles.floatingStack}>
            <FloatingOption
              icon={
                <Feather color={palette.coral} name="camera" size={16} />
              }
              iconBackground={palette.blush}
              label="Log your OOTD"
              onPress={() => navigateTo("style")}
            />
            <FloatingOption
              icon={
                <MaterialCommunityIcons color="#2F7A43" name="hanger" size={16} />
              }
              iconBackground="#F0FDF4"
              label="Add to closet"
              onPress={() => navigateTo("add")}
            />
          </View>
        </View>
      </Modal>

      <SafeAreaView edges={["bottom"]} style={styles.safeArea}>
        <View style={styles.shell}>
          <TabIcon
            active={focused === "home"}
            backgroundColor={palette.sky}
            icon={<MaterialCommunityIcons color={palette.darkText} name="tshirt-crew-outline" size={21} />}
            onPress={() => navigateTo("home")}
          />
          <TabIcon
            active={focused === "closet"}
            backgroundColor={palette.butter}
            icon={<Feather color={palette.darkText} name="grid" size={20} />}
            onPress={() => navigateTo("closet")}
          />

          <Pressable
            accessibilityRole="button"
            onPress={() => {
              void Haptics.selectionAsync();
              setMenuOpen((current) => !current);
            }}
            style={({ pressed }) => [
              styles.addOrb,
              menuOpen || focused === "add" ? styles.addOrbActive : null,
              pressed ? styles.pressed : null
            ]}
          >
            <Feather
              color={menuOpen || focused === "add" ? colors.white : palette.darkText}
              name="plus"
              size={24}
              style={menuOpen ? styles.addIconOpen : null}
            />
          </Pressable>

          <TabIcon
            active={focused === "style"}
            backgroundColor={palette.blush}
            icon={<Feather color={palette.darkText} name="book-open" size={19} />}
            onPress={() => navigateTo("style")}
          />
          <TabIcon
            active={focused === "profile"}
            backgroundColor={palette.lavender}
            icon={<Feather color={palette.darkText} name="user" size={20} />}
            onPress={() => navigateTo("profile")}
          />
        </View>
      </SafeAreaView>
    </>
  );
}

function normalizeRouteName(routeName?: string): TabKey | null {
  if (!routeName) {
    return null;
  }

  if (routeName === "index") {
    return "home";
  }

  if (routeName.startsWith("closet")) {
    return "closet";
  }

  if (routeName === "add") {
    return "add";
  }

  if (routeName === "style") {
    return "style";
  }

  if (routeName === "profile") {
    return "profile";
  }

  return null;
}

function TabIcon({
  active,
  backgroundColor,
  icon,
  onPress
}: {
  active: boolean;
  backgroundColor: string;
  icon: ReactNode;
  onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.item, pressed ? styles.pressed : null]}>
      {active ? (
        <View style={styles.activeStack}>
          <View style={[styles.activeOrb, { backgroundColor }]}>
            {icon}
          </View>
          <View style={styles.activeDot} />
        </View>
      ) : (
        <View style={styles.inactiveIcon}>{icon}</View>
      )}
    </Pressable>
  );
}

function FloatingOption({
  icon,
  iconBackground,
  label,
  onPress
}: {
  icon: ReactNode;
  iconBackground: string;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.floatingAction, pressed ? styles.pressed : null]}>
      <View style={[styles.floatingActionIcon, { backgroundColor: iconBackground }]}>{icon}</View>
      <AppText color={palette.darkText} style={styles.floatingActionLabel}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: palette.cream
  },
  modalOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: palette.overlay
  },
  floatingStack: {
    alignItems: "center",
    gap: 12,
    paddingBottom: 120
  },
  floatingAction: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    height: 48,
    paddingLeft: 16,
    paddingRight: 20,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.94)",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 18,
    elevation: 10
  },
  floatingActionIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center"
  },
  floatingActionLabel: {
    fontSize: 14,
    lineHeight: 18,
    fontFamily: "Manrope_700Bold"
  },
  shell: {
    marginHorizontal: 20,
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
    paddingHorizontal: 12,
    height: 72,
    borderRadius: 38,
    backgroundColor: palette.warmWhite,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 24,
    elevation: 12
  },
  item: {
    width: 56,
    height: 56,
    alignItems: "center",
    justifyContent: "center"
  },
  activeStack: {
    alignItems: "center",
    gap: 4
  },
  activeOrb: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 10,
    elevation: 4
  },
  activeDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: palette.darkText
  },
  inactiveIcon: {
    opacity: 0.52
  },
  addOrb: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.sage,
    shadowColor: "#7A8F69",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.24,
    shadowRadius: 12,
    elevation: 6
  },
  addOrbActive: {
    backgroundColor: palette.coral
  },
  addIconOpen: {
    transform: [{ rotate: "45deg" }]
  },
  pressed: {
    transform: [{ scale: 0.97 }]
  }
});
