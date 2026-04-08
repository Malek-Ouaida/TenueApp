"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useActionState, useEffect, useState } from "react";
import { ArrowLeft, Eye, EyeOff } from "lucide-react";

import { registerAction } from "../../actions/auth";
import { initialAuthFormState } from "../form-state";

export default function RegisterPage() {
  const [state, formAction, isPending] = useActionState(registerAction, initialAuthFormState);
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setReady(true), 50);
    return () => clearTimeout(timer);
  }, []);

  const isValid = email.length > 0 && password.length >= 6;
  const strengthLevel =
    password.length === 0 ? 0 : password.length < 4 ? 1 : password.length < 7 ? 2 : password.length < 10 ? 3 : 4;

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      <div className="hero-orb left-[8%] top-24 h-40 w-40 bg-sage/40" />
      <div className="hero-orb hero-orb-secondary bottom-20 right-[10%] h-48 w-48 bg-coral/40" />
      <div className="flex w-full max-w-md flex-col">
        <div
          className="transition-all duration-500 ease-out"
          style={{
            opacity: ready ? 1 : 0,
            transform: ready ? "translateY(0)" : "translateY(-8px)"
          }}
        >
          <button
            type="button"
            onClick={() => router.push("/")}
            className="interactive-press -ml-2 flex h-10 w-10 items-center justify-center rounded-full bg-secondary transition-all duration-200 active:scale-95"
            style={{ boxShadow: "var(--shadow-sm)" }}
          >
            <ArrowLeft className="h-[18px] w-[18px] text-foreground" />
          </button>
        </div>

        <div
          className="mt-8 transition-all duration-700 ease-out"
          style={{
            opacity: ready ? 1 : 0,
            transform: ready ? "translateY(0)" : "translateY(16px)",
            transitionDelay: "100ms"
          }}
        >
          <h1 className="font-display text-[32px] font-medium tracking-[-0.02em] text-foreground">
            Create your
            <br />
            account
          </h1>
          <p className="mt-2 font-body text-[15px] text-muted-foreground">
            Start building your wardrobe.
          </p>
        </div>

        <form action={formAction} className="mt-10 space-y-5">
          <div
            className="transition-all duration-700 ease-out"
            style={{
              opacity: ready ? 1 : 0,
              transform: ready ? "translateY(0)" : "translateY(16px)",
              transitionDelay: "200ms"
            }}
          >
            <label
              className="mb-2.5 block font-body text-[12px] font-semibold uppercase tracking-[0.08em] transition-colors duration-200"
              style={{ color: emailFocused ? "hsl(0, 76%, 70%)" : "hsl(var(--muted-foreground))" }}
              htmlFor="email"
            >
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
              className="h-[52px] w-full rounded-2xl bg-card px-5 font-body text-[15px] text-foreground outline-none transition-all duration-300"
              style={{
                border: `2px solid ${emailFocused ? "hsl(0, 76%, 70%)" : "hsl(var(--border))"}`,
                boxShadow: emailFocused ? "0 0 0 4px hsla(0, 76%, 70%, 0.08)" : "none"
              }}
              onFocus={() => setEmailFocused(true)}
              onBlur={() => setEmailFocused(false)}
            />
          </div>

          <div
            className="transition-all duration-700 ease-out"
            style={{
              opacity: ready ? 1 : 0,
              transform: ready ? "translateY(0)" : "translateY(16px)",
              transitionDelay: "300ms"
            }}
          >
            <label
              className="mb-2.5 block font-body text-[12px] font-semibold uppercase tracking-[0.08em] transition-colors duration-200"
              style={{
                color: passwordFocused ? "hsl(0, 76%, 70%)" : "hsl(var(--muted-foreground))"
              }}
              htmlFor="password"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="At least 6 characters"
                required
                className="h-[52px] w-full rounded-2xl bg-card px-5 pr-12 font-body text-[15px] text-foreground outline-none transition-all duration-300"
                style={{
                  border: `2px solid ${passwordFocused ? "hsl(0, 76%, 70%)" : "hsl(var(--border))"}`,
                  boxShadow: passwordFocused ? "0 0 0 4px hsla(0, 76%, 70%, 0.08)" : "none"
                }}
                onFocus={() => setPasswordFocused(true)}
                onBlur={() => setPasswordFocused(false)}
              />
              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground"
              >
                {showPassword ? (
                  <EyeOff className="h-[18px] w-[18px]" />
                ) : (
                  <Eye className="h-[18px] w-[18px]" />
                )}
              </button>
            </div>

            {password.length > 0 ? (
              <div className="mt-3 flex gap-1.5">
                {[1, 2, 3, 4].map((index) => (
                  <div
                    key={index}
                    className="h-[3px] flex-1 rounded-full transition-all duration-500"
                    style={{
                      background:
                        strengthLevel >= index
                          ? index <= 1
                            ? "hsl(0, 76%, 70%)"
                            : index <= 2
                              ? "hsl(46, 100%, 79%)"
                              : "hsl(140, 42%, 89%)"
                          : "hsl(var(--border))"
                    }}
                  />
                ))}
              </div>
            ) : null}
          </div>

          <div
            className="transition-all duration-700 ease-out"
            style={{ opacity: ready ? 1 : 0, transitionDelay: "400ms" }}
          >
            <p className="font-body text-[12px] leading-[1.5] text-muted-foreground">
              By continuing, you agree to our Terms of Service and Privacy Policy.
            </p>
          </div>

          {state.error ? (
            <p className="font-body text-sm text-destructive">{state.error}</p>
          ) : null}
          {state.notice ? (
            <p className="font-body text-sm text-foreground">{state.notice}</p>
          ) : null}

          <div
            className="transition-all duration-700 ease-out"
            style={{
              opacity: ready ? 1 : 0,
              transform: ready ? "translateY(0)" : "translateY(20px)",
              transitionDelay: "500ms"
            }}
          >
            <button
              type="submit"
              disabled={!isValid || isPending}
              className="button-sheen h-[56px] w-full rounded-full font-body text-[15px] font-semibold tracking-[-0.01em] transition-all duration-300 active:scale-[0.97] disabled:active:scale-100"
              style={{
                background:
                  isValid && !isPending
                    ? "linear-gradient(135deg, hsl(var(--coral)) 0%, hsl(0, 76%, 70%) 100%)"
                    : "hsl(var(--border))",
                color:
                  isValid && !isPending
                    ? "hsl(var(--primary-foreground))"
                    : "hsl(var(--muted-foreground))",
                boxShadow:
                  isValid && !isPending ? "0 12px 40px hsla(0, 76%, 70%, 0.3)" : "none"
              }}
            >
              {isPending ? "Creating Account..." : "Start your wardrobe"}
            </button>
          </div>
        </form>

        <p
          className="mt-6 text-center font-body text-sm text-muted-foreground transition-all duration-700 ease-out"
          style={{ opacity: ready ? 1 : 0, transitionDelay: "600ms" }}
        >
          Already have an account?{" "}
          <Link href="/signin" className="font-semibold text-foreground hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
