import type { ReactNode } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";

export function FilterBar({
  children,
  onReset,
}: {
  children: ReactNode;
  onReset?: () => void;
}) {
  return (
    <Card className="flex flex-wrap items-end gap-3">
      <div className="flex flex-1 flex-wrap items-end gap-3">{children}</div>
      {onReset ? (
        <Button size="sm" variant="ghost" onClick={onReset}>
          Reset Filters
        </Button>
      ) : null}
    </Card>
  );
}

export function FilterField({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="flex min-w-36 flex-col gap-1 text-xs text-stone-400">
      <span className="uppercase tracking-wide">{label}</span>
      {children}
    </label>
  );
}
