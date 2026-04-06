import { Stack, router } from "expo-router";
import { StyleSheet } from "react-native";

import { colors } from "../src/theme";
import { AppText, BrandMark, Button, Card, Screen } from "../src/ui";

export default function NotFoundScreen() {
  return (
    <>
      <Stack.Screen options={{ title: "Not Found" }} />
      <Screen>
        <BrandMark variant="wordmark" subtle />
        <Card style={styles.card} tone="soft">
          <AppText color={colors.textSubtle} variant="eyebrow">
            Wrong turn
          </AppText>
          <AppText variant="display">That route is not part of Tenue&apos;s closet flow.</AppText>
          <AppText color={colors.textMuted}>
            Return to the home dashboard and reopen the closet, review, style, or profile surface
            from there.
          </AppText>
          <Button label="Return Home" onPress={() => router.replace("/")} tone="organize" />
        </Card>
      </Screen>
    </>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: 240,
    justifyContent: "center",
    gap: 16
  }
});
