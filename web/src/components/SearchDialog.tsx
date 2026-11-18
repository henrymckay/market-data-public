import { Command } from "cmdk";
import { useEffect } from "react";

import type { Instrument } from "../lib/types";

interface SearchProps {
  open: boolean;
  instruments: readonly Instrument[];
  onClose: () => void;
  onPick: (instrument: Instrument) => void;
  /** Called as a result is highlighted, so its bars can load before Enter. */
  onHighlight?: (instrument: Instrument) => void;
  hint: string;
}

const CLASS_LABEL: Record<string, string> = {
  commodity: "Commodity",
  crypto: "Crypto",
  etf: "ETF",
  fx: "Currency",
  index: "Index",
  rate: "Rate",
  stock: "Stock",
};

/** The ticker search: opened by `/` or Cmd/Ctrl+K, a filtered list of instruments. */
export function SearchDialog({ open, instruments, onClose, onPick, onHighlight, hint }: SearchProps) {
  useEffect(() => {
    if (!open) return undefined;
    const close = (event: KeyboardEvent): void => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-start bg-black/40 px-3 pt-[12vh]" onMouseDown={onClose}>
      <div
        className="mx-auto w-full max-w-lg overflow-hidden rounded-lg border bg-popover shadow-[0_4px_16px_rgba(0,0,0,0.16)]"
        role="dialog"
        aria-label="Search instruments"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <Command
          loop
          onValueChange={(value) => {
            const ticker = value.split(" ")[0]?.toLowerCase();
            const item = instruments.find((i) => i.ticker.toLowerCase() === ticker);
            if (item !== undefined) onHighlight?.(item);
          }}
        >
          <Command.Input
            autoFocus
            placeholder="Search by ticker or name"
            className="h-12 w-full border-0 border-b bg-transparent px-4 text-base outline-none placeholder:text-muted-foreground"
          />
          <Command.List className="scroll-thin max-h-[50vh] overflow-y-auto p-1.5">
            <Command.Empty className="p-4 text-center text-sm text-muted-foreground">No instrument matches.</Command.Empty>
            {instruments.map((item) => (
              <Command.Item
                key={item.ticker}
                value={`${item.ticker} ${item.name}`}
                onSelect={() => onPick(item)}
                className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-base data-[selected=true]:bg-muted"
              >
                <span className="w-24 shrink-0 font-medium">{item.ticker}</span>
                <span className="min-w-0 flex-1 truncate text-text-2">{item.name}</span>
                <span className="shrink-0 text-sm text-muted-foreground">{CLASS_LABEL[item.assetClass] ?? item.assetClass}</span>
              </Command.Item>
            ))}
          </Command.List>
          <div className="border-t px-4 py-2 text-xs text-muted-foreground">{hint}</div>
        </Command>
      </div>
    </div>
  );
}
