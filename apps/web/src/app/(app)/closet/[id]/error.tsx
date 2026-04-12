"use client";

import Link from "next/link";
import { AlertCircle, ArrowLeft } from "lucide-react";

type ClosetItemErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ClosetItemErrorPage({ error, reset }: ClosetItemErrorPageProps) {
  return (
    <div className="page-enter">
      <Link
        href="/closet"
        className="mb-6 inline-flex items-center gap-2 font-body text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back to closet
      </Link>

      <div
        className="rounded-3xl border border-border bg-card px-6 py-10 text-center"
        style={{ boxShadow: "var(--shadow-sm)" }}
      >
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
          <AlertCircle className="h-5 w-5 text-foreground" />
        </div>
        <h1 className="mb-2 font-display text-2xl font-semibold tracking-editorial text-foreground">
          Closet item could not load
        </h1>
        <p className="mx-auto max-w-md font-body text-sm text-muted-foreground">
          {error.message || "Something went wrong while loading this item."}
        </p>
        <button
          className="mt-5 inline-flex h-11 items-center justify-center rounded-full bg-foreground px-5 font-body text-sm font-semibold text-background transition-opacity hover:opacity-90"
          onClick={() => reset()}
          type="button"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
