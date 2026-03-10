import type { ReactNode } from "react";
import { Button } from "./ui/button";
import { cn } from "../lib/utils";

export interface AppNavItem {
  id: string;
  label: string;
  path: string;
  shortcut: string;
}

export interface AppShellProps {
  navItems: AppNavItem[];
  activePath: string;
  onNavigate: (path: string) => void;
  onOpenCommandPalette: () => void;
  siteSwitcher: ReactNode;
  rightRail: ReactNode;
  headerActions?: ReactNode;
  themeMode?: "polarized-dark" | "polarized-light";
  onToggleThemeMode?: () => void;
  children: ReactNode;
}

export function AppShell({
  navItems,
  activePath,
  onNavigate,
  onOpenCommandPalette,
  siteSwitcher,
  rightRail,
  headerActions,
  themeMode = "polarized-dark",
  onToggleThemeMode,
  children,
}: AppShellProps) {
  const isDarkTheme = themeMode === "polarized-dark";

  return (
    <div
      className={cn(
        "min-h-screen",
        isDarkTheme ? "theme-polarized-dark" : "theme-polarized-light",
        isDarkTheme
          ? "bg-[radial-gradient(circle_at_12%_5%,rgba(34,211,238,0.12),transparent_30%),radial-gradient(circle_at_90%_92%,rgba(245,158,11,0.08),transparent_26%),linear-gradient(180deg,#11100f_0%,#0b0a09_100%)] text-stone-100"
          : "bg-[radial-gradient(circle_at_12%_5%,rgba(8,145,178,0.16),transparent_30%),radial-gradient(circle_at_88%_88%,rgba(245,158,11,0.14),transparent_28%),linear-gradient(180deg,#f8fafc_0%,#f1f5f9_100%)] text-slate-900",
      )}
    >
      <div className="mx-auto grid min-h-screen max-w-[1680px] grid-cols-1 gap-3 p-3 lg:grid-cols-[280px_minmax(0,1fr)_320px]">
        <aside
          className={cn(
            "hidden rounded-xl border p-4 lg:flex lg:flex-col lg:gap-4",
            isDarkTheme ? "border-stone-700/90 bg-stone-900/80" : "border-slate-300 bg-white/85",
          )}
        >
          <div className={cn("border-b pb-3", isDarkTheme ? "border-stone-700" : "border-slate-300")}>
            <p className={cn("text-sm font-semibold tracking-wide", isDarkTheme ? "text-stone-200" : "text-slate-800")}>Qaongdur Ops</p>
            <p className={cn("mt-1 text-xs", isDarkTheme ? "text-stone-500" : "text-slate-500")}>Vision VMS Console</p>
          </div>
          {siteSwitcher}
          <nav className="space-y-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.path)}
                className={cn(
                  "flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors",
                  activePath === item.path
                    ? isDarkTheme
                      ? "bg-cyan-900/40 text-cyan-100"
                      : "bg-cyan-100 text-cyan-900"
                    : isDarkTheme
                      ? "text-stone-300 hover:bg-stone-800/80"
                      : "text-slate-600 hover:bg-slate-100",
                )}
              >
                <span>{item.label}</span>
                <span className={cn("font-mono text-[10px]", isDarkTheme ? "text-stone-500" : "text-slate-400")}>{item.shortcut}</span>
              </button>
            ))}
          </nav>
          <div className={cn("mt-auto rounded-md border p-2", isDarkTheme ? "border-stone-700 bg-stone-950/70" : "border-slate-300 bg-slate-50/90")}>
            <p className={cn("text-[11px]", isDarkTheme ? "text-stone-500" : "text-slate-500")}>Global command palette</p>
            <Button
              size="sm"
              variant="secondary"
              onClick={onOpenCommandPalette}
              className="mt-2 w-full"
            >
              Open (Ctrl/Cmd + K)
            </Button>
          </div>
        </aside>

        <div className="flex min-h-[calc(100vh-1.5rem)] flex-col gap-3 overflow-hidden">
          <header className={cn("flex flex-wrap items-center justify-between gap-2 rounded-xl border px-3 py-2", isDarkTheme ? "border-stone-700/90 bg-stone-900/70" : "border-slate-300 bg-white/80")}>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 overflow-x-auto">
                {navItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onNavigate(item.path)}
                    className={cn(
                      "whitespace-nowrap rounded-md px-3 py-1.5 text-xs transition-colors",
                      activePath === item.path
                        ? isDarkTheme
                          ? "bg-cyan-900/40 text-cyan-100"
                          : "bg-cyan-100 text-cyan-900"
                        : isDarkTheme
                          ? "text-stone-400 hover:bg-stone-800/80"
                          : "text-slate-500 hover:bg-slate-100",
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              {headerActions}
            </div>
            <div className="flex items-center gap-2">
              {onToggleThemeMode && (
                <Button size="sm" variant="secondary" onClick={onToggleThemeMode}>
                  {isDarkTheme ? "Theme / Light" : "Theme / Dark"}
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={onOpenCommandPalette}>
                Command Palette
              </Button>
            </div>
          </header>
          <main className={cn("flex-1 overflow-auto rounded-xl border p-3", isDarkTheme ? "border-stone-700/90 bg-stone-900/60" : "border-slate-300 bg-white/75")}>
            {children}
          </main>
        </div>

        <aside className={cn("hidden rounded-xl border p-3 lg:block", isDarkTheme ? "border-stone-700/90 bg-stone-900/80" : "border-slate-300 bg-white/85")}>
          {rightRail}
        </aside>
      </div>
    </div>
  );
}
