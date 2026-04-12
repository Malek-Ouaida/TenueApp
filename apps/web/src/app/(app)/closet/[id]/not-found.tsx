import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function ClosetItemNotFoundPage() {
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
        <h1 className="mb-2 font-display text-2xl font-semibold tracking-editorial text-foreground">
          Closet item not found
        </h1>
        <p className="mx-auto max-w-md font-body text-sm text-muted-foreground">
          This item may have been archived, removed, or never belonged to this account.
        </p>
      </div>
    </div>
  );
}
