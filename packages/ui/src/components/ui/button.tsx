import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--qa-button-default-bg)] text-[var(--qa-button-default-text)] hover:bg-[var(--qa-button-default-hover)] focus-visible:ring-stone-400",
        secondary:
          "bg-[var(--qa-button-secondary-bg)] text-[var(--qa-button-secondary-text)] hover:bg-[var(--qa-button-secondary-hover)] focus-visible:ring-cyan-600",
        ghost:
          "bg-transparent text-[var(--qa-button-ghost-text)] hover:bg-[var(--qa-button-ghost-hover-bg)] focus-visible:ring-cyan-600",
        attention:
          "bg-amber-500 text-stone-950 hover:bg-amber-400 focus-visible:ring-amber-300",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-9 px-4",
        lg: "h-10 px-5",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}
