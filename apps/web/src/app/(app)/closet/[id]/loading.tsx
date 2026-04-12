import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function ClosetItemLoadingPage() {
  return (
    <div className="page-enter animate-pulse">
      <Link
        href="/closet"
        className="mb-6 inline-flex items-center gap-2 font-body text-sm text-muted-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back to closet
      </Link>

      <div className="grid gap-8 md:grid-cols-2">
        <div className="aspect-[4/5] rounded-3xl bg-secondary" />
        <div className="space-y-6">
          <div className="space-y-2">
            <div className="h-10 w-3/4 rounded-full bg-secondary" />
            <div className="h-4 w-1/2 rounded-full bg-secondary" />
          </div>

          <div className="rounded-2xl bg-card p-5" style={{ boxShadow: "var(--shadow-sm)" }}>
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-4 rounded-full bg-secondary" />
              ))}
            </div>
          </div>

          <div className="rounded-2xl bg-card p-5" style={{ boxShadow: "var(--shadow-sm)" }}>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="h-16 rounded-2xl bg-secondary" />
              <div className="h-16 rounded-2xl bg-secondary" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
