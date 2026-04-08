import { useEffect } from "react";
import { Stack, useRouter, useSegments, type Href } from "expo-router";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { OutfitsProvider } from "../src/outfits/provider";
import { AuthProvider, useAuth } from "../src/auth/provider";
import { colors, useAppFonts } from "../src/theme";
import { AppText, BrandMark } from "../src/ui";

function RootNavigator() {
  const { status } = useAuth();
  const router = useRouter();
  const segments = useSegments();
  const [fontsLoaded] = useAppFonts();

  useEffect(() => {
    if (status === "loading" || !fontsLoaded) {
      return;
    }

    const firstSegment = segments[0];
    const isAuthRoute = firstSegment === "(auth)" || firstSegment === "profile-setup";

    if (status === "anonymous" && !isAuthRoute) {
      router.replace("/splash" as Href);
    }

    if (status === "authenticated" && isAuthRoute) {
      router.replace("/" as Href);
    }
  }, [fontsLoaded, router, segments, status]);

  if (status === "loading" || !fontsLoaded) {
    return (
      <View style={styles.loadingScreen}>
        <BrandMark />
        <View style={styles.loadingCopy}>
          <AppText color={colors.textSubtle} variant="eyebrow">
            Preparing your closet
          </AppText>
          <AppText variant="display">Loading Tenue.</AppText>
          <AppText color={colors.textMuted}>
            Restoring your session, loading the light-mode design system, and bringing the closet
            shell back into focus.
          </AppText>
        </View>
        <ActivityIndicator color={colors.text} size="large" />
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: {
          backgroundColor: colors.background
        }
      }}
    />
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <OutfitsProvider>
        <RootNavigator />
      </OutfitsProvider>
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 18,
    paddingHorizontal: 28,
    backgroundColor: colors.background
  },
  loadingCopy: {
    gap: 8,
    alignItems: "center"
  }
});
