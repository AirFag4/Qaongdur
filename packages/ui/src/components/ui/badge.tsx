import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-medium uppercase tracking-wide",
  {
    variants: {
      tone: {
        stone: "border-stone-600 bg-stone-800 text-stone-200",
        cyan: "border-cyan-800 bg-cyan-950/70 text-cyan-200",
        amber: "border-amber-700 bg-amber-950/60 text-amber-200",
        red: "border-red-800 bg-red-950/60 text-red-200",
        emerald: "border-emerald-700 bg-emerald-950/60 text-emerald-200",
      },
    },
    defaultVariants: {
      tone: "stone",
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
