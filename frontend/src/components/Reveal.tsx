import type { ReactNode } from "react";

import { cn } from "@/components/ui/utils";

interface RevealProps {
  children: ReactNode;
  delay?: number;
  className?: string;
}

export function Reveal({ children, delay = 0, className }: RevealProps) {
  return (
    <div
      style={{ animationDelay: `${delay}ms` }}
      className={cn(
        "motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-3 motion-safe:fill-mode-both motion-safe:duration-500 motion-safe:ease-out",
        className,
      )}
    >
      {children}
    </div>
  );
}
