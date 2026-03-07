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
  children,
}: AppShellProps) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_12%_5%,rgba(34,211,238,0.12),transparent_30%),radial-gradient(circle_at_90%_92%,rgba(245,158,11,0.08),transparent_26%),linear-gradient(180deg,#11100f_0%,#0b0a09_100%)] text-stone-100">
      <div className="mx-auto grid min-h-screen max-w-[1680px] grid-cols-1 gap-3 p-3 lg:grid-cols-[280px_minmax(0,1fr)_320px]">
        <aside className="hidden rounded-xl border border-stone-700/90 bg-stone-900/80 p-4 lg:flex lg:flex-col lg:gap-4">
          <div className="border-b border-stone-700 pb-3">
            <p className="text-sm font-semibold tracking-wide text-stone-200">Qaongdur Ops</p>
            <p className="mt-1 text-xs text-stone-500">Vision VMS Console</p>
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
                    ? "bg-cyan-900/40 text-cyan-100"
                    : "text-stone-300 hover:bg-stone-800/80",
                )}
              >
                <span>{item.label}</span>
                <span className="font-mono text-[10px] text-stone-500">{item.shortcut}</span>
              </button>
            ))}
          </nav>
          <div className="mt-auto rounded-md border border-stone-700 bg-stone-950/70 p-2">
            <p className="text-[11px] text-stone-500">Global command palette</p>
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
          <header className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-stone-700/90 bg-stone-900/70 px-3 py-2">
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
                        ? "bg-cyan-900/40 text-cyan-100"
                        : "text-stone-400 hover:bg-stone-800/80",
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              {headerActions}
            </div>
            <Button size="sm" variant="ghost" onClick={onOpenCommandPalette}>
              Command Palette
            </Button>
          </header>
          <main className="flex-1 overflow-auto rounded-xl border border-stone-700/90 bg-stone-900/60 p-3">
            {children}
          </main>
        </div>

        <aside className="hidden rounded-xl border border-stone-700/90 bg-stone-900/80 p-3 lg:block">
          {rightRail}
        </aside>
      </div>
    </div>
  );
}
