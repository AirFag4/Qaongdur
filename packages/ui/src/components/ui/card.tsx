import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border p-4 shadow-[0_10px_40px_-20px_rgba(0,0,0,0.7)] backdrop-blur border-[var(--qa-card-border)] bg-[var(--qa-card-bg)] text-[var(--qa-panel-text)]",
        className,
      )}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cn("text-sm font-semibold text-[var(--qa-card-title)]", className)} {...props} />
  );
}

export function CardDescription({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-xs text-[var(--qa-card-description)]", className)} {...props} />;
}
