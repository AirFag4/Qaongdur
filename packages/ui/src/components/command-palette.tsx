import { useEffect, useMemo, useState } from "react";
import { Card } from "./ui/card";

export interface CommandPaletteItem {
  id: string;
  label: string;
  group: string;
  shortcut?: string;
  run: () => void;
}

export function CommandPalette({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: CommandPaletteItem[];
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const normalized = query.toLowerCase().trim();
    if (!normalized) {
      return items;
    }
    return items.filter((item) =>
      `${item.label} ${item.group}`.toLowerCase().includes(normalized),
    );
  }, [items, query]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[120] bg-black/70 p-4 backdrop-blur-sm">
      <div className="mx-auto mt-20 max-w-2xl">
        <Card className="space-y-3 border-stone-600 bg-stone-950/95">
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search commands..."
            className="h-10 w-full rounded-md border border-stone-700 bg-stone-900 px-3 text-sm text-stone-100 outline-none focus:border-cyan-700"
          />
          <div className="max-h-[55vh] space-y-1 overflow-auto">
            {filtered.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  item.run();
                  onClose();
                }}
                className="flex w-full items-center justify-between rounded-md border border-stone-800 px-3 py-2 text-left transition-colors hover:border-cyan-700 hover:bg-stone-900"
              >
                <div>
                  <p className="text-sm text-stone-100">{item.label}</p>
                  <p className="text-[11px] uppercase tracking-wide text-stone-500">
                    {item.group}
                  </p>
                </div>
                {item.shortcut ? (
                  <span className="font-mono text-[10px] text-stone-500">{item.shortcut}</span>
                ) : null}
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
