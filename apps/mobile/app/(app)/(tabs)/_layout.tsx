import { Tabs } from "expo-router";

import { colors } from "../../../src/theme";
import { TenueTabBar } from "../../../src/ui";

export default function TabLayout() {
  return (
    <Tabs
      tabBar={(props) => <TenueTabBar {...props} />}
      screenOptions={{
        headerShown: false,
        sceneStyle: {
          backgroundColor: colors.background
        }
      }}
    >
      <Tabs.Screen name="index" />
      <Tabs.Screen name="closet/index" options={{ title: "Closet" }} />
      <Tabs.Screen name="add" />
      <Tabs.Screen name="style" />
      <Tabs.Screen name="profile" />
    </Tabs>
  );
}
