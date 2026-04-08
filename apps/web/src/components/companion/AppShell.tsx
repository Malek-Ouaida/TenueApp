"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useState } from "react";
import { BarChart3, BookOpen, Menu, Shirt, User, X } from "lucide-react";

import { COMPANION_ASSETS } from "@/lib/companion-data";

const NAV_ITEMS = [
  { label: "Closet", path: "/closet", icon: Shirt },
  { label: "Stats", path: "/stats", icon: BarChart3 },
  { label: "Lookbook", path: "/lookbook", icon: BookOpen },
  { label: "Profile", path: "/profile", icon: User }
] as const;

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <header
        className="nav-shell-enter sticky top-0 z-50 border-b border-border bg-cream/75 glass-frost"
        style={{ boxShadow: "var(--shadow-sm)" }}
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link href="/dashboard" className="flex items-center gap-2 transition-transform duration-300 hover:-translate-y-0.5">
            <img src={COMPANION_ASSETS.logo} alt="Tenue" className="h-6" />
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {NAV_ITEMS.map((item) => {
              const active = pathname.startsWith(item.path);

              return (
                <Link
                  key={item.path}
                  href={item.path}
                  className={`nav-pill rounded-full px-4 py-2 font-body text-sm font-medium ${
                    active
                      ? "nav-pill-active bg-foreground text-primary-foreground"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <button
            type="button"
            onClick={() => setMobileOpen((current) => !current)}
            className="interactive-press flex h-10 w-10 items-center justify-center rounded-full bg-card md:hidden"
            style={{ boxShadow: "var(--shadow-sm)" }}
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {mobileOpen ? (
          <div className="panel-pop space-y-1 border-t border-border bg-card/95 px-6 py-4 backdrop-blur-xl md:hidden">
            {NAV_ITEMS.map((item) => {
              const active = pathname.startsWith(item.path);

              return (
                <Link
                  key={item.path}
                  href={item.path}
                  onClick={() => setMobileOpen(false)}
                  className={`nav-pill flex items-center gap-3 rounded-2xl px-4 py-3 font-body text-sm font-medium ${
                    active
                      ? "nav-pill-active bg-foreground text-primary-foreground"
                      : "text-foreground hover:bg-secondary"
                  }`}
                  style={{
                    animation: `revealSlideRight 560ms var(--ease-soft) ${60 + NAV_ITEMS.indexOf(item) * 70}ms both`
                  }}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ) : null}
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  );
}
