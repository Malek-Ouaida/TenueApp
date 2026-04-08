"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  ArrowLeft,
  Bell,
  BookOpen,
  ChevronRight,
  Heart,
  HelpCircle,
  Lock,
  LogOut,
  Palette,
  Shield,
  User
} from "lucide-react";

import { logoutAction } from "../../actions/auth";

const SECTIONS = [
  {
    title: "Personal",
    items: [
      { label: "Edit profile", icon: User },
      { label: "Style preferences", icon: Palette },
      { label: "Saved items", icon: Heart },
      { label: "Lookbook", icon: BookOpen, route: "/lookbook" }
    ]
  },
  {
    title: "App",
    items: [
      { label: "Notifications", icon: Bell },
      { label: "Privacy & media", icon: Shield },
      { label: "Account & security", icon: Lock }
    ]
  },
  {
    title: "Support",
    items: [{ label: "Help & support", icon: HelpCircle }]
  }
] as const;

export default function SettingsPage() {
  const router = useRouter();
  const [showSignOut, setShowSignOut] = useState(false);

  return (
    <div className="page-enter mx-auto max-w-2xl">
      <button
        type="button"
        onClick={() => router.back()}
        className="interactive-press mb-6 flex items-center gap-2 font-body text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back
      </button>

      <h1 className="mb-8 font-display text-4xl font-semibold tracking-editorial text-foreground">
        Settings
      </h1>

      {SECTIONS.map((section) => (
        <div key={section.title} className="mb-6">
          <h3 className="mb-2 font-body text-xs uppercase tracking-wider text-muted-foreground">
            {section.title}
          </h3>
          <div className="overflow-hidden rounded-3xl bg-card" style={{ boxShadow: "var(--shadow-sm)" }}>
            {section.items.map((item, index) => (
              <button
                key={item.label}
                type="button"
                onClick={() => {
                  if ("route" in item && item.route) {
                    router.push(item.route);
                  }
                }}
                className="interactive-press flex w-full items-center gap-3 px-5 py-4 transition-colors hover:bg-secondary/50"
                style={
                  index < section.items.length - 1
                    ? { borderBottom: "1px solid hsl(var(--border))" }
                    : undefined
                }
              >
                <item.icon className="h-[18px] w-[18px] text-muted-foreground" />
                <span className="flex-1 text-left font-body text-sm text-foreground">
                  {item.label}
                </span>
                <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
              </button>
            ))}
          </div>
        </div>
      ))}

      <div className="mt-4">
        {!showSignOut ? (
          <button
            type="button"
            onClick={() => setShowSignOut(true)}
            className="interactive-press flex w-full items-center gap-3 rounded-3xl bg-card px-5 py-4 transition-colors hover:bg-secondary/50"
            style={{ boxShadow: "var(--shadow-sm)" }}
          >
            <LogOut className="h-[18px] w-[18px] text-destructive" />
            <span className="font-body text-sm text-destructive">Sign out</span>
          </button>
        ) : (
          <div className="rounded-3xl bg-card p-5" style={{ boxShadow: "var(--shadow-sm)" }}>
            <p className="mb-1 font-body text-sm font-medium text-foreground">Sign out?</p>
            <p className="mb-4 font-body text-xs text-muted-foreground">
              You&apos;ll need to sign in again to access your closet.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setShowSignOut(false)}
                className="interactive-press h-11 flex-1 rounded-2xl bg-secondary font-body text-sm font-medium text-foreground transition-colors hover:bg-secondary/80"
              >
                Cancel
              </button>
              <form action={logoutAction} className="flex-1">
                <button
                  type="submit"
                  className="interactive-press h-11 w-full rounded-2xl bg-destructive font-body text-sm font-medium text-destructive-foreground transition-colors hover:bg-destructive/90"
                >
                  Sign out
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
