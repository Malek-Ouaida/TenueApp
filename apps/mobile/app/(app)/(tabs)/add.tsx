import * as Haptics from "expo-haptics";
import { router, type Href } from "expo-router";
import { StyleSheet, View } from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useClosetUpload } from "../../../src/closet/hooks";
import { colors, spacing } from "../../../src/theme";
import {
  AppText,
  BrandMark,
  Button,
  Card,
  Chip,
  Screen
} from "../../../src/ui";

export default function AddScreen() {
  const { session } = useAuth();
  const upload = useClosetUpload(session?.access_token);

  async function handleSource(source: "camera" | "library") {
    try {
      await Haptics.selectionAsync();
      const draft = await upload.selectAndUpload(source);
      if (!draft) {
        return;
      }

      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
  }

  async function retryUpload() {
    try {
      const draft = await upload.retryLastUpload();
      if (!draft) {
        return;
      }

      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
  }

  return (
    <Screen>
      <BrandMark variant="wordmark" subtle />

      <Card tone="soft">
        <AppText color={colors.textSubtle} variant="eyebrow">
          Add
        </AppText>
        <AppText variant="display">Choose the right intent before anything touches the wardrobe.</AppText>
        <AppText color={colors.textMuted}>
          Tenue separates closet ingestion from lookbook saves so review stays trustworthy and the
          confirmed closet stays calm.
        </AppText>
      </Card>

      <Card tone="spotlight" style={styles.flowCard}>
        <Chip label="Primary flow" tone="spotlight" />
        <AppText variant="title">Add to Closet</AppText>
        <AppText color={colors.textMuted}>
          Single garment photo, immediate upload, then processing and review until you confirm it
          into the closet.
        </AppText>
        <View style={styles.buttonStack}>
          <Button
            label="Use Camera"
            loading={upload.isUploading}
            onPress={() => void handleSource("camera")}
            tone="organize"
          />
          <Button
            label="Photo Library"
            onPress={() => void handleSource("library")}
            variant="secondary"
            disabled={upload.isUploading}
          />
        </View>
        {upload.stage ? (
          <View style={styles.notice}>
            <AppText color={colors.textSubtle} variant="captionStrong">
              Upload status
            </AppText>
            <AppText variant="bodyStrong">{upload.stage}</AppText>
            {upload.stage === "Sent to processing" ? (
              <>
                <AppText color={colors.textMuted}>
                  Keep uploading. Tenue will move ready items into confirmation automatically.
                </AppText>
                <Button
                  label="Open Processing"
                  onPress={() => router.push("/closet?tab=processing" as Href)}
                  size="sm"
                  variant="secondary"
                />
              </>
            ) : null}
          </View>
        ) : null}
        {upload.error ? (
          <View style={styles.notice}>
            <AppText color={colors.danger}>{upload.error}</AppText>
            <Button
              label="Retry last upload"
              onPress={() => void retryUpload()}
              size="sm"
              variant="secondary"
            />
          </View>
        ) : null}
      </Card>

      <Card tone="lookbook" style={styles.flowCard}>
        <Chip label="Lookbook preview" tone="lookbook" />
        <AppText variant="title">Save to Lookbook</AppText>
        <AppText color={colors.textMuted}>
          Outfit photos, mirror looks, styled moments, and inspiration images belong here, not in
          closet review. The polished shell is ready; sync lands in a later slice.
        </AppText>
        <View style={styles.lookbookRow}>
          <Chip label="Mirror photo" tone="lookbook" />
          <Chip label="Styled look" tone="lookbook" />
          <Chip label="Inspiration" tone="lookbook" />
        </View>
        <Button label="Coming Soon" onPress={() => {}} variant="secondary" disabled />
      </Card>

      <Card tone="review">
        <AppText color={colors.textSubtle} variant="eyebrow">
          Review-first product truth
        </AppText>
        <AppText variant="sectionTitle">Nothing skips confirmation.</AppText>
        <AppText color={colors.textMuted}>
          Category and subcategory remain the minimum gate before anything becomes canonical closet
          data.
        </AppText>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  flowCard: {
    gap: spacing.md
  },
  buttonStack: {
    gap: spacing.sm
  },
  notice: {
    gap: spacing.xs
  },
  lookbookRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  }
});
