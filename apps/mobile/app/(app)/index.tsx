import { StatusBar } from "expo-status-bar";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../../src/auth/provider";

export default function AuthenticatedHomeScreen() {
  const { logoutCurrentUser, user } = useAuth();

  async function handleLogout() {
    await logoutCurrentUser();
    router.replace("/login");
  }

  return (
    <View style={styles.screen}>
      <StatusBar style="dark" />
      <Text style={styles.eyebrow}>Protected Shell</Text>
      <Text style={styles.title}>Welcome back</Text>
      <Text style={styles.copy}>
        {user?.email ?? "Unknown user"} is authenticated through the API-owned auth contract.
      </Text>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Current scope</Text>
        <Text style={styles.cardValue}>`GET /auth/me` resolved successfully.</Text>
      </View>

      <Pressable style={styles.secondaryButton} onPress={() => void handleLogout()}>
        <Text style={styles.secondaryButtonLabel}>Sign out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: 24,
    backgroundColor: "#f6f2eb"
  },
  eyebrow: {
    marginBottom: 10,
    color: "#8b6f48",
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 2.4,
    textTransform: "uppercase"
  },
  title: {
    color: "#1f1a15",
    fontSize: 34,
    fontWeight: "700",
    marginBottom: 12
  },
  copy: {
    color: "#564b3f",
    fontSize: 16,
    lineHeight: 24,
    marginBottom: 24,
    maxWidth: 320
  },
  card: {
    borderRadius: 22,
    padding: 20,
    backgroundColor: "rgba(255, 255, 255, 0.82)",
    borderWidth: 1,
    borderColor: "rgba(31, 26, 21, 0.08)",
    marginBottom: 20
  },
  cardLabel: {
    color: "#8b6f48",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.6,
    textTransform: "uppercase",
    marginBottom: 8
  },
  cardValue: {
    color: "#1f1a15",
    fontSize: 16,
    lineHeight: 24
  },
  secondaryButton: {
    minHeight: 52,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(31, 26, 21, 0.08)"
  },
  secondaryButtonLabel: {
    color: "#1f1a15",
    fontSize: 15,
    fontWeight: "700"
  }
});
