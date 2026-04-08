import * as Haptics from "expo-haptics";

import { isIosSimulator } from "./runtime";

async function runHaptic(effect: () => Promise<void>) {
  if (isIosSimulator) {
    return;
  }

  try {
    await effect();
  } catch {
    // Haptics are optional UX polish and should not surface runtime noise.
  }
}

export function triggerSelectionHaptic() {
  return runHaptic(() => Haptics.selectionAsync());
}

export function triggerSuccessHaptic() {
  return runHaptic(() =>
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)
  );
}

export function triggerErrorHaptic() {
  return runHaptic(() =>
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error)
  );
}
