import { Link, Stack } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

export default function NotFoundScreen() {
  return (
    <>
      <Stack.Screen options={{ title: "Not Found" }} />
      <View style={styles.screen}>
        <Text style={styles.title}>Route not found</Text>
        <Link href="/" style={styles.link}>
          Return to the scaffold home
        </Link>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
    backgroundColor: "#f6f2eb"
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: "#211d18",
    marginBottom: 12
  },
  link: {
    color: "#7b6a52",
    fontSize: 16,
    fontWeight: "600"
  }
});
