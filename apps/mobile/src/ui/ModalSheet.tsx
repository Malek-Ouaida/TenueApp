import { BlurView } from "expo-blur";
import type { PropsWithChildren, ReactNode } from "react";
import { Modal, Pressable, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { colors, radius, spacing } from "../theme";

type ModalSheetProps = PropsWithChildren<{
  footer?: ReactNode;
  onClose: () => void;
  visible: boolean;
}>;

export function ModalSheet({ children, footer, onClose, visible }: ModalSheetProps) {
  const insets = useSafeAreaInsets();

  return (
    <Modal transparent animationType="slide" visible={visible} onRequestClose={onClose}>
      <Pressable style={styles.overlay} onPress={onClose}>
        <BlurView intensity={18} tint="light" style={StyleSheet.absoluteFillObject} />
      </Pressable>
      <View style={[styles.sheet, { paddingBottom: spacing.lg + insets.bottom }]}>
        <View style={styles.handle} />
        <View style={styles.body}>{children}</View>
        {footer ? <View style={styles.footer}>{footer}</View> : null}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: colors.surfaceOverlay
  },
  sheet: {
    marginTop: "auto",
    backgroundColor: colors.surfaceElevated,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.lg
  },
  handle: {
    alignSelf: "center",
    width: 48,
    height: 4,
    borderRadius: 999,
    backgroundColor: "rgba(23, 20, 17, 0.16)"
  },
  body: {
    gap: spacing.md
  },
  footer: {
    gap: spacing.sm
  }
});
