import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { resolveSession } from "../../lib/auth/session";

type AuthLayoutProps = {
  children: ReactNode;
};

export default async function AuthLayout({ children }: AuthLayoutProps) {
  const session = await resolveSession();
  if (session) {
    redirect("/profile");
  }

  return children;
}
