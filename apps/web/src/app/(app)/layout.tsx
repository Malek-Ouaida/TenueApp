import type { ReactNode } from "react";

import { AppShell } from "@/components/companion/AppShell";
import { requireSession } from "../../lib/auth/session";

type AppLayoutProps = {
  children: ReactNode;
};

export default async function AppLayout({ children }: AppLayoutProps) {
  await requireSession();

  return <AppShell>{children}</AppShell>;
}
