import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, type Href } from "expo-router";
import { useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View
} from "react-native";

import { AppText } from "../ui";
import { EmptyPhotoState } from "../ui/feature-components";
import { launchCameraForSingleImage } from "../media/picker";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";

export default function AddLookbookEntryScreen() {
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [context, setContext] = useState("");
  const [notes, setNotes] = useState("");
  const [date, setDate] = useState("2026-04-05");

  async function handlePhotoPick() {
    const uri = await launchCameraForSingleImage();
    if (!uri) {
      return;
    }

    setPhotoUri(uri);
  }

  return (
    <ScrollView
      bounces={false}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      style={styles.screen}
    >
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.headerButton}>
          <Feather color={featurePalette.foreground} name="arrow-left" size={18} />
        </Pressable>
        <Pressable disabled={!photoUri} onPress={() => router.push("/lookbook" as Href)} style={styles.saveButton}>
          <AppText style={[styles.saveLabel, !photoUri ? styles.saveLabelDisabled : null]}>Save</AppText>
        </Pressable>
      </View>

      <AppText style={styles.title}>New entry</AppText>

      {photoUri ? (
        <Pressable onPress={() => void handlePhotoPick()} style={styles.photoFrame}>
          <Image contentFit="cover" source={{ uri: photoUri }} style={styles.photoImage} />
        </Pressable>
      ) : (
        <EmptyPhotoState
          label="Add a photo"
          onPress={() => void handlePhotoPick()}
          subtitle="Tap to capture an image"
        />
      )}

      <View style={styles.form}>
        <InputRow
          icon="tag"
          onChangeText={setContext}
          placeholder="What's the occasion?"
          value={context}
        />
        <InputRow
          icon="calendar"
          onChangeText={setDate}
          placeholder="Date"
          value={date}
        />
        <TextInput
          multiline
          onChangeText={setNotes}
          placeholder="Notes (optional)"
          placeholderTextColor={featurePalette.muted}
          style={styles.notes}
          textAlignVertical="top"
          value={notes}
        />
      </View>
    </ScrollView>
  );
}

function InputRow({
  icon,
  onChangeText,
  placeholder,
  value
}: {
  icon: "calendar" | "tag";
  onChangeText: (value: string) => void;
  placeholder: string;
  value: string;
}) {
  return (
    <View style={[styles.inputRow, featureShadows.sm]}>
      <Feather color={featurePalette.muted} name={icon} size={16} />
      <TextInput
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={featurePalette.muted}
        style={styles.input}
        value={value}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  content: {
    paddingTop: 56,
    paddingHorizontal: 24,
    paddingBottom: 32,
    gap: 20
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  headerButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.9)",
    alignItems: "center",
    justifyContent: "center",
    ...featureShadows.sm
  },
  saveButton: {
    minWidth: 48,
    alignItems: "flex-end"
  },
  saveLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  saveLabelDisabled: {
    opacity: 0.3
  },
  title: {
    ...featureTypography.title
  },
  photoFrame: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: 24,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  photoImage: {
    width: "100%",
    height: "100%"
  },
  form: {
    gap: 16
  },
  inputRow: {
    height: 48,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  input: {
    flex: 1,
    fontFamily: "Manrope_500Medium",
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  notes: {
    minHeight: 112,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontFamily: "Manrope_500Medium",
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground,
    ...featureShadows.sm
  }
});
