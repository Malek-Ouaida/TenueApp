import { Redirect, type Href } from "expo-router";

export default function SignInAliasRoute() {
  return <Redirect href={"/login" as Href} />;
}
