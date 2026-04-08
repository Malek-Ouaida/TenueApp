import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { getSessionRecoveryPath, resolveSession } from "../../lib/auth/session";

type AuthLayoutProps = {
  children: ReactNode;
};

export default async function AuthLayout({ children }: AuthLayoutProps) {
  const session = await resolveSession();
  if (session.status === "authenticated") {
    redirect("/dashboard");
  }

  if (session.status === "refresh-required") {
    redirect(getSessionRecoveryPath());
  }

  return children;
}
