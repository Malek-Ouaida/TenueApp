import Link from "next/link";
import { ArrowRight, BarChart3, BookOpen, Crown, Flame, Palette, Shirt, Tag } from "lucide-react";

import { RevealSection } from "@/components/companion/RevealSection";
import { COMPANION_ASSETS } from "@/lib/companion-data";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-cream">
      <div className="hero-orb left-[8%] top-24 h-36 w-36 bg-coral/50" />
      <div className="hero-orb hero-orb-secondary right-[12%] top-40 h-44 w-44 bg-sage/45" />
      <div className="hero-orb bottom-[18%] left-[20%] h-28 w-28 bg-lavender/45" />

      <header className="nav-shell-enter sticky top-0 z-50 border-b border-border bg-cream/80 glass-frost">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <img src={COMPANION_ASSETS.logo} alt="Tenue" className="h-6" />
          <Link
            href="/dashboard"
            className="button-sheen rounded-full bg-foreground px-5 py-2.5 font-body text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            Open App
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-6 pb-24 pt-16">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <RevealSection duration={920} distance={28}>
            <h1 className="mb-6 font-display text-5xl font-semibold leading-[1.05] tracking-editorial text-foreground md:text-6xl lg:text-7xl">
              Your wardrobe,
              <br />
              <span className="italic">beautifully</span>
              <br />
              curated.
            </h1>
            <p className="mb-8 max-w-md font-body text-lg leading-relaxed text-muted-foreground">
              Tenue helps you organize your closet, discover your style patterns, and dress with
              intention - every day.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/register"
                className="button-sheen inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3.5 font-body text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
                style={{ boxShadow: "var(--shadow-md)" }}
              >
                Get Started
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="#features"
                className="button-sheen inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-3.5 font-body text-sm font-semibold text-foreground transition-colors hover:bg-secondary"
              >
                Learn More
              </a>
            </div>
          </RevealSection>

          <RevealSection delay={180} duration={980} variant="scale" className="relative">
            <div className="hero-photo aspect-[3/4] overflow-hidden rounded-3xl" style={{ boxShadow: "var(--shadow-lg)" }}>
              <img
                src={COMPANION_ASSETS.hero}
                alt="Fashion editorial"
                className="h-full w-full object-cover"
              />
            </div>
            <div
              className="floating-card absolute -bottom-6 -left-6 hidden items-center gap-3 rounded-2xl bg-card/90 p-4 md:flex"
              style={{ boxShadow: "var(--shadow-md)" }}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sage">
                <Shirt className="h-5 w-5 text-foreground" />
              </div>
              <div>
                <p className="font-body text-sm font-bold text-foreground">10 items</p>
                <p className="font-body text-xs text-muted-foreground">in your closet</p>
              </div>
            </div>
          </RevealSection>
        </div>
      </section>

      <section id="features" className="bg-card py-28">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid items-center gap-16 lg:grid-cols-2">
            <RevealSection duration={860} distance={24}>
              <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-sage">
                <Shirt className="h-7 w-7 text-foreground" />
              </div>
              <h2 className="mb-4 font-display text-4xl font-semibold leading-[1.1] tracking-editorial text-foreground md:text-5xl">
                Your entire closet,
                <br />
                <span className="italic">one scroll away.</span>
              </h2>
              <p className="max-w-md font-body text-lg leading-relaxed text-muted-foreground">
                Browse by category, color, or season. Every piece in your wardrobe, beautifully
                organized and always at your fingertips.
              </p>
            </RevealSection>

            <RevealSection delay={140} duration={900} variant="right">
              <div className="grid grid-cols-3 gap-3">
                {COMPANION_ASSETS.recentLooks.map((image, index) => (
                  <div
                    key={image}
                    className="card-lift aspect-[3/4] overflow-hidden rounded-2xl"
                    style={{
                      boxShadow: "var(--shadow-md)",
                      transform: index === 1 ? "translateY(-12px)" : "none"
                    }}
                  >
                    <img src={image} alt="Closet item" className="h-full w-full object-cover" />
                  </div>
                ))}
              </div>
            </RevealSection>
          </div>
        </div>
      </section>

      <section className="py-28">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid items-center gap-16 lg:grid-cols-2">
            <RevealSection className="order-2 lg:order-1" duration={880} variant="left">
              <div className="grid grid-cols-2 gap-3">
                {[
                  {
                    icon: <Shirt className="h-5 w-5" />,
                    label: "Total Items",
                    value: "127",
                    sub: "in your closet",
                    color: "bg-lavender/30"
                  },
                  {
                    icon: <Crown className="h-5 w-5 text-butter" />,
                    label: "Most Worn",
                    value: "Oversized Blazer",
                    sub: "14 times · Zara",
                    color: "bg-butter/20"
                  },
                  {
                    icon: <Palette className="h-5 w-5 text-butter" />,
                    label: "Top Color",
                    value: "Black",
                    sub: "32 items",
                    color: "bg-butter/20"
                  },
                  {
                    icon: <Tag className="h-5 w-5 text-coral" />,
                    label: "Favorite Brand",
                    value: "Zara",
                    sub: "18 items",
                    color: "bg-coral/10"
                  },
                  {
                    icon: <Flame className="h-5 w-5 text-coral" />,
                    label: "Current Streak",
                    value: "5 days",
                    sub: "your best: 12 days",
                    color: "bg-coral/15"
                  },
                  {
                    icon: <BarChart3 className="h-5 w-5" />,
                    label: "Outfits Logged",
                    value: "47",
                    sub: "since January 2026",
                    color: "bg-sage"
                  }
                ].map((stat) => (
                  <div
                    key={stat.label}
                    className="card-lift flex items-center gap-3 rounded-2xl bg-card p-4"
                    style={{ boxShadow: "var(--shadow-sm)" }}
                  >
                    <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full ${stat.color}`}>
                      {stat.icon}
                    </div>
                    <div className="min-w-0">
                      <p className="font-body text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        {stat.label}
                      </p>
                      <p className="truncate font-body text-base font-bold leading-tight text-foreground">
                        {stat.value}
                      </p>
                      {stat.sub ? (
                        <p className="font-body text-[11px] text-muted-foreground">{stat.sub}</p>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </RevealSection>

            <RevealSection className="order-1 lg:order-2" delay={120} duration={860}>
              <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-lavender">
                <BarChart3 className="h-7 w-7 text-foreground" />
              </div>
              <h2 className="mb-4 font-display text-4xl font-semibold leading-[1.1] tracking-editorial text-foreground md:text-5xl">
                Know your
                <br />
                <span className="italic">style patterns.</span>
              </h2>
              <p className="max-w-md font-body text-lg leading-relaxed text-muted-foreground">
                Discover which pieces you reach for most, your favorite brands, and how much value
                you&apos;re getting from every item.
              </p>
            </RevealSection>
          </div>
        </div>
      </section>

      <section className="bg-card py-28">
        <div className="mx-auto max-w-7xl px-6 text-center">
          <RevealSection duration={860}>
            <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-coral">
              <BookOpen className="h-7 w-7 text-foreground" />
            </div>
            <h2 className="mb-4 font-display text-4xl font-semibold leading-[1.1] tracking-editorial text-foreground md:text-5xl">
              Your best fits,
              <br />
              <span className="italic">all in one place.</span>
            </h2>
            <p className="mx-auto mb-12 max-w-lg font-body text-lg leading-relaxed text-muted-foreground">
              A visual diary of outfits you&apos;ve loved. Revisit what worked, find inspiration,
              and never forget a great look.
            </p>
          </RevealSection>

          <RevealSection delay={160} duration={920} variant="scale">
            <div className="mx-auto grid max-w-3xl grid-cols-3 gap-4">
              {COMPANION_ASSETS.recentLooks.map((look, index) => (
                <div
                  key={look}
                  className={`card-lift aspect-[3/4] overflow-hidden rounded-2xl ${
                    index === 1 ? "floating-card floating-card-delay" : ""
                  }`}
                  style={{ boxShadow: "var(--shadow-md)" }}
                >
                  <img src={look} alt={`Look ${index + 1}`} className="h-full w-full object-cover" />
                </div>
              ))}
            </div>
          </RevealSection>
        </div>
      </section>

      <section className="bg-foreground py-24">
        <RevealSection className="mx-auto max-w-7xl px-6 text-center" duration={960} variant="scale">
          <h2 className="mb-4 font-display text-4xl font-semibold leading-[1.1] tracking-editorial text-primary-foreground md:text-6xl">
            Your wardrobe
            <br />
            <span className="italic">deserves this.</span>
          </h2>
          <p className="mx-auto mb-10 max-w-md font-body text-lg leading-relaxed text-primary-foreground/60">
            Join Tenue and start dressing with intention - every single day.
          </p>
          <Link
            href="/register"
            className="button-sheen inline-flex items-center gap-2 rounded-full bg-card px-8 py-4 font-body text-base font-semibold text-foreground transition-opacity hover:opacity-90"
            style={{ boxShadow: "var(--shadow-lg)" }}
          >
            Get Started
            <ArrowRight className="h-5 w-5" />
          </Link>
        </RevealSection>
      </section>

      <footer className="border-t border-border bg-cream py-20">
        <RevealSection className="flex items-center justify-center" duration={860} variant="scale">
          <img
            src={COMPANION_ASSETS.logo}
            alt="Tenue"
            className="w-[clamp(200px,40vw,500px)] select-none"
          />
        </RevealSection>
      </footer>
    </div>
  );
}
