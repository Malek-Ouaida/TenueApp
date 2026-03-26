import { Link, router } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";

import { useAuth } from "../../src/auth/provider";

export default function LoginScreen() {
  const { loginWithPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setIsSubmitting(true);
    setError(null);

    const result = await loginWithPassword(email, password);
    setIsSubmitting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    router.replace("/");
  }

  return (
    <View style={styles.screen}>
      <StatusBar style="dark" />
      <Text style={styles.eyebrow}>Phase 3.2</Text>
      <Text style={styles.title}>Sign in to Tenue</Text>
      <Text style={styles.copy}>
        Auth foundation is live. Use your account to unlock the protected shell.
      </Text>

      <View style={styles.form}>
        <TextInput
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          placeholder="Email"
          placeholderTextColor="#8b7e70"
          style={styles.input}
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          autoCapitalize="none"
          autoComplete="password"
          placeholder="Password"
          placeholderTextColor="#8b7e70"
          secureTextEntry
          style={styles.input}
          value={password}
          onChangeText={setPassword}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable style={styles.primaryButton} onPress={() => void handleSubmit()} disabled={isSubmitting}>
          {isSubmitting ? (
            <ActivityIndicator color="#fcfaf6" />
          ) : (
            <Text style={styles.primaryButtonLabel}>Sign in</Text>
          )}
        </Pressable>
      </View>

      <Text style={styles.secondaryCopy}>
        New here?{" "}
        <Link href="/register" style={styles.link}>
          Create an account
        </Link>
      </Text>
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
    marginBottom: 28,
    maxWidth: 320
  },
  form: {
    gap: 12
  },
  input: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(31, 26, 21, 0.08)",
    backgroundColor: "rgba(255, 255, 255, 0.82)",
    paddingHorizontal: 16,
    paddingVertical: 16,
    color: "#1f1a15",
    fontSize: 16
  },
  error: {
    color: "#a53f33",
    fontSize: 14,
    lineHeight: 20
  },
  primaryButton: {
    marginTop: 8,
    minHeight: 56,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 18,
    backgroundColor: "#1f1a15"
  },
  primaryButtonLabel: {
    color: "#fcfaf6",
    fontSize: 16,
    fontWeight: "700"
  },
  secondaryCopy: {
    marginTop: 24,
    color: "#564b3f",
    fontSize: 15
  },
  link: {
    color: "#8b6f48",
    fontWeight: "700"
  }
});
