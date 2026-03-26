import { Redirect } from "expo-router";

export default function AuthenticatedHomeScreen() {
  return <Redirect href="./profile" />;
}
