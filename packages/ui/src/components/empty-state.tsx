import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-52 flex-col items-center justify-center rounded-xl border border-dashed border-[var(--qa-empty-border)] bg-[var(--qa-empty-bg)] p-6 text-center">
      <p className="text-sm font-semibold text-[var(--qa-empty-title)]">{title}</p>
      <p className="mt-2 max-w-sm text-xs text-[var(--qa-empty-description)]">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
