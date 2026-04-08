"use client";

import type { ReactNode } from "react";

import { useScrollReveal } from "@/hooks/useScrollReveal";

const sr = "will-change-transform";
const srHidden = "";
const srVisible = "";

type RevealSectionProps = {
  children: ReactNode;
  className?: string;
  delay?: number;
  duration?: number;
  distance?: number;
  variant?: "up" | "scale" | "left" | "right";
};

export function RevealSection({
  children,
  className = "",
  delay = 0,
  duration = 820,
  distance = 22,
  variant = "up"
}: RevealSectionProps) {
  const { ref, isVisible } = useScrollReveal(0.12);

  return (
    <div
      ref={ref}
      data-visible={isVisible ? "true" : "false"}
      data-variant={variant}
      className={`reveal-section ${sr} ${isVisible ? srVisible : srHidden} ${className}`}
      style={{
        transitionDelay: `${delay}ms`,
        animationDelay: `${delay}ms`,
        ["--reveal-distance" as string]: `${distance}px`,
        ["--reveal-duration" as string]: `${duration}ms`
      }}
    >
      {children}
    </div>
  );
}
