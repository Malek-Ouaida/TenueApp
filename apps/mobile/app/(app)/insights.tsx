import { Redirect, type Href } from "expo-router";

export default function InsightsAliasRoute() {
  return <Redirect href={"/stats" as Href} />;
}
