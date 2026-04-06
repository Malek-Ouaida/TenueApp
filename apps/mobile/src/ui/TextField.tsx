import { StyleSheet, TextInput, View, type TextInputProps } from "react-native";

import { colors, radius, spacing } from "../theme";
import { AppText } from "./Typography";

type TextFieldProps = TextInputProps & {
  label: string;
  helper?: string | null;
  error?: string | null;
};

export function TextField({ error, helper, label, style, ...props }: TextFieldProps) {
  return (
    <View style={styles.root}>
      <AppText variant="captionStrong" color={colors.textSubtle}>
        {label}
      </AppText>
      <TextInput
        {...props}
        placeholderTextColor={colors.textSubtle}
        style={[styles.input, style]}
      />
      {error ? (
        <AppText color={colors.danger} variant="caption">
          {error}
        </AppText>
      ) : helper ? (
        <AppText color={colors.textSubtle} variant="caption">
          {helper}
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    gap: spacing.sm
  },
  input: {
    minHeight: 58,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceElevated,
    color: colors.text,
    fontFamily: "Manrope_500Medium",
    fontSize: 16
  }
});
