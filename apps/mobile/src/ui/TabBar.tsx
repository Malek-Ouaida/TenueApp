import { Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, radius, shadows, spacing } from "../theme";
import { AppText } from "./Typography";

const labels: Record<string, string> = {
  index: "Home",
  closet: "Closet",
  add: "Add",
  style: "Style",
  profile: "Profile"
};

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

export function TenueTabBar({ descriptors, navigation, state }: TenueTabBarProps) {
  return (
    <SafeAreaView edges={["bottom"]} style={styles.safeArea}>
      <View style={styles.shell}>
        {state.routes.map((route, index) => {
          const descriptor = descriptors[route.key];
          const label = labels[route.name] ?? descriptor.options.title ?? route.name;
          const isFocused = state.index === index;
          const isAdd = route.name === "add";

          return (
            <Pressable
              key={route.key}
              accessibilityRole="button"
              accessibilityState={isFocused ? { selected: true } : {}}
              onPress={() => navigation.navigate(route.name)}
              style={[styles.item, isAdd ? styles.addItem : null]}
            >
              {isAdd ? (
                <View style={styles.addOrb}>
                  <AppText color={colors.white} variant="title">
                    +
                  </AppText>
                </View>
              ) : (
                <View style={[styles.dot, isFocused ? styles.dotActive : null]} />
              )}
              <AppText
                color={isFocused || isAdd ? colors.text : colors.textSubtle}
                variant="tabLabel"
              >
                {label}
              </AppText>
            </Pressable>
          );
        })}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: colors.background
  },
  shell: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    borderRadius: radius.xl,
    backgroundColor: "rgba(255, 253, 250, 0.96)",
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    ...shadows.soft
  },
  item: {
    flex: 1,
    minHeight: 58,
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 8,
    paddingBottom: 4
  },
  addItem: {
    transform: [{ translateY: -14 }]
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: "rgba(23, 20, 17, 0.12)"
  },
  dotActive: {
    width: 24,
    backgroundColor: colors.text
  },
  addOrb: {
    width: 56,
    height: 56,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.text,
    borderWidth: 1,
    borderColor: "rgba(23, 20, 17, 0.08)"
  }
});
