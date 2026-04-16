import { Redirect, type Href } from "expo-router";

export default function AddRoute() {
  return <Redirect href={"/closet?tab=processing" as Href} />;
}
