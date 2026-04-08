import { redirect } from "next/navigation";

export default function ProtectedHomePage() {
  redirect("/dashboard");
}
