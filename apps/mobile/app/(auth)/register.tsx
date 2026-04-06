import { Link, router } from "expo-router";
import { useState } from "react";
import { StyleSheet, View } from "react-native";

import { useAuth } from "../../src/auth/provider";
import { colors, spacing } from "../../src/theme";
import { AppText, BrandMark, Button, Card, Screen, TextField } from "../../src/ui";

export default function RegisterScreen() {
  const { registerWithPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setIsSubmitting(true);
    setError(null);
    setNotice(null);

    const result = await registerWithPassword(email, password);
    setIsSubmitting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    if (result.nextStep === "authenticated") {
      router.replace("/");
      return;
    }

    setPassword("");
    setNotice(result.message);
  }

  return (
    <Screen scrollable={false}>
      <View style={styles.authShell}>
        <BrandMark />
        <Card tone="soft" style={styles.heroCard}>
          <AppText color={colors.textSubtle} variant="eyebrow">
            Closet-first setup
          </AppText>
          <AppText variant="display">Capture once. Review calmly. Confirm with intention.</AppText>
          <AppText color={colors.textMuted}>
            Create your Tenue account to keep uploads private, preserve review state, and build a
            wardrobe that downstream intelligence can actually trust.
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
            autoComplete="new-password"
            helper="Use a password you can keep on this device while testing the mobile flow."
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
          {notice ? (
            <AppText color={colors.success} variant="caption">
              {notice}
            </AppText>
          ) : null}

          <Button label="Create Account" loading={isSubmitting} onPress={() => void handleSubmit()} />

          <AppText color={colors.textMuted} variant="caption">
            Already registered?{" "}
            <Link href="/login" style={styles.link}>
              Sign in
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
