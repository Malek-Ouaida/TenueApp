import { Redirect, type Href } from "expo-router";

export default function HomeAliasRoute() {
  return <Redirect href={"/" as Href} />;
}
