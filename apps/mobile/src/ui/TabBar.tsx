import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { BlurView } from "expo-blur";
import { router, type Href } from "expo-router";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Animated,
  Modal,
  Pressable,
  StyleSheet,
  View,
  type ViewStyle
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { useOutfits } from "../outfits/provider";
import { useAuth } from "../auth/provider";
import { selectImagesFromLibrary, selectSingleImage, uploadClosetAssets } from "../closet/upload";
import { featurePalette, featureShadows } from "../theme/feature";
import { launchCameraForSingleImage } from "../media/picker";
import {
  triggerErrorHaptic,
  triggerSelectionHaptic,
  triggerSuccessHaptic
} from "../lib/haptics";
import { AppText } from "./Typography";

type TabKey = "home" | "closet" | "lookbook" | "profile";

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

const ACTIVE_BACKGROUNDS: Record<TabKey, string> = {
  home: featurePalette.sky,
  closet: featurePalette.butter,
  lookbook: "#FFD2C2",
  profile: featurePalette.lavender
};

const TAB_ITEMS: Array<{
  key: TabKey;
  icon: ReactNode;
}> = [
  {
    key: "home",
    icon: (
      <MaterialCommunityIcons
        color={featurePalette.darkText}
        name="tshirt-crew-outline"
        size={21}
      />
    )
  },
  {
    key: "closet",
    icon: <Feather color={featurePalette.darkText} name="grid" size={20} />
  },
  {
    key: "lookbook",
    icon: <Feather color={featurePalette.darkText} name="book-open" size={19} />
  },
  {
    key: "profile",
    icon: <Feather color={featurePalette.darkText} name="user" size={20} />
  }
];

export function TenueTabBar({ navigation, state }: TenueTabBarProps) {
  const insets = useSafeAreaInsets();
  const { session } = useAuth();
  const { setLogOutfitPhotoUri } = useOutfits();

  const [menuOpen, setMenuOpen] = useState(false);
  const [closetExpanded, setClosetExpanded] = useState(false);
  const menuProgress = useRef(new Animated.Value(0)).current;
  const closetProgress = useRef(new Animated.Value(0)).current;

  const routeMap = useMemo(() => {
    const nextMap = new Map<TabKey, string>();

    state.routes.forEach((route) => {
      const normalized = normalizeRouteName(route.name);
      if (normalized) {
        if (normalized === "home" && nextMap.get("home") === "index" && route.name !== "index") {
          return;
        }

        nextMap.set(normalized, route.name);
      }
    });

    return nextMap;
  }, [state.routes]);

  const focused = normalizeRouteName(state.routes[state.index]?.name);

  useEffect(() => {
    Animated.spring(menuProgress, {
      toValue: menuOpen ? 1 : 0,
      damping: 18,
      mass: 0.8,
      stiffness: 200,
      useNativeDriver: true
    }).start();
  }, [menuOpen, menuProgress]);

  useEffect(() => {
    Animated.spring(closetProgress, {
      toValue: closetExpanded ? 1 : 0,
      damping: 18,
      mass: 0.8,
      stiffness: 220,
      useNativeDriver: true
    }).start();
  }, [closetExpanded, closetProgress]);

  function navigateTo(target: TabKey) {
    const routeName = routeMap.get(target);
    if (!routeName) {
      return;
    }

    setMenuOpen(false);
    setClosetExpanded(false);
    void triggerSelectionHaptic();
    navigation.navigate(routeName);
  }

  function closeMenu() {
    setMenuOpen(false);
    setClosetExpanded(false);
  }

  async function handleOotdPhoto() {
    closeMenu();
    await delay(150);

    try {
      const uri = await launchCameraForSingleImage();
      if (!uri) {
        return;
      }

      setLogOutfitPhotoUri(uri);
      await triggerSuccessHaptic();
      router.push(({ pathname: "/log-outfit", params: { mode: "photo" } } as unknown) as Href);
    } catch {
      await triggerErrorHaptic();
    }
  }

  async function handleGallery() {
    closeMenu();
    await delay(150);

    try {
      if (!session?.access_token) {
        return;
      }

      const assets = await selectImagesFromLibrary({ multiple: true, selectionLimit: 10 });
      if (!assets.length) {
        return;
      }

      const drafts = await uploadClosetAssets({
        accessToken: session.access_token,
        assets
      });
      await triggerSuccessHaptic();
      router.push((drafts.length === 1 ? `/review/${drafts[0]?.id}` : "/review") as Href);
    } catch {
      await triggerErrorHaptic();
    }
  }

  async function handleCamera() {
    closeMenu();
    await delay(150);

    try {
      if (!session?.access_token) {
        return;
      }

      const asset = await selectSingleImage("camera");
      if (!asset) {
        return;
      }

      const [draft] = await uploadClosetAssets({
        accessToken: session.access_token,
        assets: [asset]
      });
      if (!draft) {
        return;
      }

      await triggerSuccessHaptic();
      router.push(`/review/${draft.id}` as Href);
    } catch {
      await triggerErrorHaptic();
    }
  }

  return (
    <>
      <Modal
        animationType="none"
        onRequestClose={closeMenu}
        transparent
        visible={menuOpen}
      >
        <View style={styles.modalRoot}>
          <Pressable
            onPress={() => {
              if (closetExpanded) {
                setClosetExpanded(false);
                return;
              }

              closeMenu();
            }}
            style={StyleSheet.absoluteFillObject}
          >
            <BlurView intensity={18} style={StyleSheet.absoluteFillObject} tint="light" />
            <Animated.View
              style={[
                StyleSheet.absoluteFillObject,
                styles.modalOverlay,
                {
                  opacity: menuProgress.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0, 1]
                  })
                }
              ]}
            />
          </Pressable>

          <View style={[styles.floatingStack, { paddingBottom: insets.bottom + 100 }]}>
            <Animated.View
              style={[
                styles.floatingRow,
                buildFloatingStyle(menuProgress, {
                  hiddenScale: 0.8,
                  hiddenTranslateY: 24,
                  visibleDelay: 0.08
                })
              ]}
            >
              <FloatingOption
                icon={<Feather color={featurePalette.coral} name="camera" size={16} />}
                iconBackground={featurePalette.coralSurface}
                label="Log your OOTD"
                onPress={() => void handleOotdPhoto()}
              />
            </Animated.View>

            <Animated.View
              style={[
                styles.floatingRow,
                buildFloatingStyle(menuProgress, {
                  hiddenScale: 0.8,
                  hiddenTranslateY: 16,
                  visibleDelay: 0
                })
              ]}
            >
              <Animated.View
                style={[
                  styles.closetCollapsed,
                  {
                    opacity: closetProgress.interpolate({
                      inputRange: [0, 1],
                      outputRange: [1, 0]
                    }),
                    transform: [
                      {
                        scaleX: closetProgress.interpolate({
                          inputRange: [0, 1],
                          outputRange: [1, 1.1]
                        })
                      },
                      {
                        scaleY: closetProgress.interpolate({
                          inputRange: [0, 1],
                          outputRange: [1, 0.8]
                        })
                      }
                    ]
                  }
                ]}
              >
                <FloatingOption
                  icon={
                    <MaterialCommunityIcons
                      color="#10B981"
                      name="hanger"
                      size={16}
                    />
                  }
                  iconBackground="#F0FDF4"
                  label="Add to closet"
                  onPress={() => setClosetExpanded(true)}
                />
              </Animated.View>

              <Animated.View
                style={[
                  styles.closetExpanded,
                  {
                    opacity: closetProgress,
                    transform: [
                      {
                        scaleX: closetProgress.interpolate({
                          inputRange: [0, 1],
                          outputRange: [0.5, 1]
                        })
                      },
                      {
                        scaleY: closetProgress.interpolate({
                          inputRange: [0, 1],
                          outputRange: [0.8, 1]
                        })
                      }
                    ]
                  }
                ]}
              >
                <RoundFloatingAction
                  icon={<Feather color="#10B981" name="image" size={20} />}
                  onPress={() => void handleGallery()}
                />
                <RoundFloatingAction
                  icon={<Feather color="#10B981" name="camera" size={20} />}
                  onPress={() => void handleCamera()}
                />
              </Animated.View>
            </Animated.View>
          </View>
        </View>
      </Modal>

      <SafeAreaView edges={["bottom"]} style={styles.safeArea}>
        <View style={[styles.shell, featureShadows.nav]}>
          {TAB_ITEMS.slice(0, 2).map((item) => (
            <TabIcon
              key={item.key}
              active={focused === item.key}
              backgroundColor={ACTIVE_BACKGROUNDS[item.key]}
              icon={item.icon}
              onPress={() => navigateTo(item.key)}
            />
          ))}

          <Pressable
            accessibilityRole="button"
            onPress={() => {
              void triggerSelectionHaptic();
              if (menuOpen) {
                closeMenu();
                return;
              }

              setMenuOpen(true);
              setClosetExpanded(false);
            }}
            style={({ pressed }) => [
              styles.addOrb,
              menuOpen ? styles.addOrbActive : null,
              pressed ? styles.pressed : null
            ]}
          >
            <Animated.View
              style={{
                transform: [
                  {
                    rotate: menuProgress.interpolate({
                      inputRange: [0, 1],
                      outputRange: ["0deg", "45deg"]
                    })
                  }
                ]
              }}
            >
              <Feather
                color={menuOpen ? "#FFFFFF" : featurePalette.darkText}
                name="plus"
                size={24}
              />
            </Animated.View>
          </Pressable>

          {TAB_ITEMS.slice(2).map((item) => (
            <TabIcon
              key={item.key}
              active={focused === item.key}
              backgroundColor={ACTIVE_BACKGROUNDS[item.key]}
              icon={item.icon}
              onPress={() => navigateTo(item.key)}
            />
          ))}
        </View>
      </SafeAreaView>
    </>
  );
}

function normalizeRouteName(routeName?: string): TabKey | null {
  if (!routeName) {
    return null;
  }

  if (routeName === "index" || routeName === "home") {
    return "home";
  }

  if (routeName.startsWith("closet")) {
    return "closet";
  }

  if (routeName.startsWith("lookbook")) {
    return "lookbook";
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
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.item, pressed ? styles.pressed : null]}
    >
      {active ? (
        <View style={styles.activeStack}>
          <View style={[styles.activeOrb, { backgroundColor }]}>{icon}</View>
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
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.floatingAction, pressed ? styles.pressed : null]}
    >
      <View style={[styles.floatingActionIcon, { backgroundColor: iconBackground }]}>{icon}</View>
      <AppText style={styles.floatingActionLabel}>{label}</AppText>
    </Pressable>
  );
}

function RoundFloatingAction({
  icon,
  onPress
}: {
  icon: ReactNode;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.roundAction, pressed ? styles.pressed : null]}
    >
      {icon}
    </Pressable>
  );
}

function buildFloatingStyle(
  progress: Animated.Value,
  options: { hiddenScale: number; hiddenTranslateY: number; visibleDelay: number }
): Animated.WithAnimatedObject<ViewStyle> {
  return {
    opacity: progress.interpolate({
      inputRange: [0, 1],
      outputRange: [0, 1]
    }),
    transform: [
      {
        translateY: progress.interpolate({
          inputRange: [0, 1],
          outputRange: [options.hiddenTranslateY, 0]
        })
      },
      {
        scale: progress.interpolate({
          inputRange: [0, 1],
          outputRange: [options.hiddenScale, 1]
        })
      }
    ]
  };
}

function delay(ms: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: featurePalette.background
  },
  modalRoot: {
    flex: 1,
    justifyContent: "flex-end"
  },
  modalOverlay: {
    backgroundColor: featurePalette.overlayStrong
  },
  floatingStack: {
    alignItems: "center",
    gap: 10
  },
  floatingRow: {
    alignItems: "center",
    justifyContent: "center"
  },
  floatingAction: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    height: 48,
    paddingLeft: 16,
    paddingRight: 20,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.95)",
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
    color: featurePalette.darkText
  },
  closetCollapsed: {
    alignItems: "center",
    justifyContent: "center"
  },
  closetExpanded: {
    position: "absolute",
    flexDirection: "row",
    gap: 10
  },
  roundAction: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.95)",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 18,
    elevation: 10
  },
  shell: {
    marginHorizontal: 20,
    marginBottom: 20,
    height: 72,
    borderRadius: 38,
    backgroundColor: featurePalette.card,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    paddingHorizontal: 12
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
    backgroundColor: featurePalette.darkText
  },
  inactiveIcon: {
    opacity: 0.6
  },
  addOrb: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: featurePalette.sage,
    shadowColor: "#93B684",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 12,
    elevation: 6
  },
  addOrbActive: {
    backgroundColor: featurePalette.coral
  },
  pressed: {
    transform: [{ scale: 0.96 }]
  }
});
