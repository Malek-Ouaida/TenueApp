import { Stack } from "expo-router";

import { colors } from "../../src/theme";

export default function AppStackLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: {
          backgroundColor: colors.background
        }
      }}
    >
      <Stack.Screen name="(tabs)" />
      <Stack.Screen
        name="insights"
        options={{
          presentation: "modal"
        }}
      />
    </Stack>
  );
}
