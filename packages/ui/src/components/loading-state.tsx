export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="theme-panel-subtle flex min-h-52 items-center justify-center rounded-xl">
      <div className="theme-panel-description flex items-center gap-2 text-xs">
        <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
        {label}
      </div>
    </div>
  );
}
