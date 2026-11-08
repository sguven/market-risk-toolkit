import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-[var(--rl-radius)] border border-border-strong bg-surface px-3 text-sm text-ink placeholder:text-faint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 tnum",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("block text-xs font-medium text-muted mb-1", className)} {...props} />;
}

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-9 w-full rounded-[var(--rl-radius)] border border-border-strong bg-surface px-2.5 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40",
        className,
      )}
      {...props}
    />
  );
}
