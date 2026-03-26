import { useEffect } from "react";
import { Stack, useRouter, useSegments } from "expo-router";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { AuthProvider, useAuth } from "../src/auth/provider";

function RootNavigator() {
  const { status } = useAuth();
  const router = useRouter();
  const segments = useSegments();

  useEffect(() => {
    if (status === "loading") {
      return;
    }

    const firstSegment = segments[0];
    const isAuthRoute = firstSegment === "(auth)";

    if (status === "anonymous" && !isAuthRoute) {
      router.replace("/login");
    }

    if (status === "authenticated" && isAuthRoute) {
      router.replace("/");
    }
  }, [router, segments, status]);

  if (status === "loading") {
    return (
      <View style={styles.loadingScreen}>
        <ActivityIndicator color="#1f1a15" size="large" />
        <Text style={styles.loadingCopy}>Restoring your Tenue session…</Text>
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: {
          backgroundColor: "#f6f2eb"
        }
      }}
    />
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootNavigator />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    backgroundColor: "#f6f2eb"
  },
  loadingCopy: {
    color: "#564b3f",
    fontSize: 16
  }
});
