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
      <Tabs.Screen name="home" options={{ href: null }} />
      <Tabs.Screen name="closet/index" options={{ title: "Closet" }} />
      <Tabs.Screen name="lookbook/index" options={{ title: "Lookbook" }} />
      <Tabs.Screen name="profile" />
      <Tabs.Screen name="add" options={{ href: null }} />
      <Tabs.Screen name="style" options={{ href: null }} />
    </Tabs>
  );
}
