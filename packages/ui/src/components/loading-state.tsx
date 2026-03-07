export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex min-h-52 items-center justify-center rounded-xl border border-stone-700 bg-stone-900/40">
      <div className="flex items-center gap-2 text-xs text-stone-400">
        <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
        {label}
      </div>
    </div>
  );
}
