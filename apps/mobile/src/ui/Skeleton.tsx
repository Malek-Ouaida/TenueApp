import { StyleSheet, View, type ViewStyle } from "react-native";

import { colors, radius } from "../theme";

type SkeletonBlockProps = {
  height: number;
  style?: ViewStyle;
  width?: ViewStyle["width"];
};

export function SkeletonBlock({ height, style, width = "100%" }: SkeletonBlockProps) {
  return <View style={[styles.block, { height, width }, style]} />;
}

const styles = StyleSheet.create({
  block: {
    borderRadius: radius.md,
    backgroundColor: "rgba(23, 20, 17, 0.05)",
    borderWidth: 1,
    borderColor: colors.border
  }
});
