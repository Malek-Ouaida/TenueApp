import { Link, router } from "expo-router";
import { useState } from "react";
import { StyleSheet, View } from "react-native";

import { useAuth } from "../../src/auth/provider";
import { colors, spacing } from "../../src/theme";
import { AppText, BrandMark, Button, Card, Screen, TextField } from "../../src/ui";

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
    <Screen scrollable={false}>
      <View style={styles.authShell}>
        <BrandMark />
        <Card tone="soft" style={styles.heroCard}>
          <AppText color={colors.textSubtle} variant="eyebrow">
            Light-mode hero
          </AppText>
          <AppText variant="display">Your wardrobe becomes useful when review stays intentional.</AppText>
          <AppText color={colors.textMuted}>
            Sign in to move from upload to review to confirmed closet data without ever letting AI
            suggestions quietly become truth.
          </AppText>
        </Card>

        <Card tone="soft" style={styles.formCard}>
          <TextField
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            label="Email"
            placeholder="you@example.com"
            value={email}
            onChangeText={setEmail}
          />
          <TextField
            autoCapitalize="none"
            autoComplete="password"
            label="Password"
            placeholder="Password"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          {error ? (
            <AppText color={colors.danger} variant="caption">
              {error}
            </AppText>
          ) : null}

          <Button label="Sign In" loading={isSubmitting} onPress={() => void handleSubmit()} />

          <AppText color={colors.textMuted} variant="caption">
            New here?{" "}
            <Link href="/register" style={styles.link}>
              Create an account
            </Link>
          </AppText>
        </Card>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  authShell: {
    flex: 1,
    justifyContent: "space-between",
    paddingBottom: spacing.xl
  },
  heroCard: {
    marginTop: spacing.xl,
    gap: spacing.md
  },
  formCard: {
    gap: spacing.md
  },
  link: {
    color: colors.text,
    fontFamily: "Manrope_700Bold"
  }
});
