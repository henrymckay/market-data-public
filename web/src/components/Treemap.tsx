import { useEffect, useMemo, useRef, useState } from "react";

import { diverging, inkOn } from "../lib/color";
import { formatCompact, formatPercent } from "../lib/format";
import type { Tokens } from "../lib/theme";
import { squarify } from "../lib/treemap";

export interface Leaf {
  ticker: string;
  name: string;
  sector: string;
  value: number;
  ret: number;
}

interface TreemapProps {
  leaves: readonly Leaf[];
  bound: number;
  tokens: Tokens;
  periodWords: string;
  onOpen: (ticker: string) => void;
}

const SHORT: Record<string, string> = {
  "Communication Services": "Communication",
  "Consumer Discretionary": "Discretionary",
  "Consumer Staples": "Staples",
};
const GAP = 2;
const HEADER = 18;

/** Stocks as nested tiles: sectors by traded value, each stock sized by its own, coloured by return. */
export function Treemap({ leaves, bound, tokens: t, periodWords, onOpen }: TreemapProps) {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ h: 0, w: 0 });
  const [tip, setTip] = useState<{ leaf: Leaf; x: number; y: number } | null>(null);

  useEffect(() => {
    const element = box.current!;
    const measure = (): void => setSize({ h: element.clientHeight, w: element.clientWidth });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const layout = useMemo(() => {
    const sectors = new Map<string, Leaf[]>();
    for (const leaf of leaves) sectors.set(leaf.sector, [...(sectors.get(leaf.sector) ?? []), leaf]);
    const parents = [...sectors.entries()].map(([name, children]) => ({ children, name, value: children.reduce((s, c) => s + c.value, 0) }));
    return squarify(parents, { h: size.h, w: size.w, x: 0, y: 0 }).map((sector) => {
      const inner = { h: sector.h - HEADER - GAP, w: sector.w - GAP, x: sector.x + GAP / 2, y: sector.y + HEADER };
      return { ...sector, tiles: squarify(sector.children, inner) };
    });
  }, [leaves, size]);

  return (
    <div ref={box} role="group" aria-label={`Stocks by sector, coloured by return over ${periodWords}; each tile opens its instrument`} className="relative h-[320px] w-full overflow-hidden sm:h-[460px]" onMouseLeave={() => setTip(null)}>
      {layout.map((sector) => (
        <div key={sector.name}>
          <div className="absolute truncate pr-1 text-xs font-medium text-text-2" style={{ height: HEADER, left: sector.x + GAP / 2, lineHeight: `${HEADER}px`, top: sector.y, width: Math.max(0, sector.w - GAP) }}>
            {sector.w > 150 ? sector.name : sector.w > 56 ? (SHORT[sector.name] ?? sector.name) : ""}
          </div>
          {sector.tiles.map((tile) => {
            const fill = diverging(tile.ret, bound, t);
            const ink = inkOn(fill, "#ffffff", "#000000");
            const w = tile.w - GAP;
            const h = tile.h - GAP;
            return (
              <button
                key={tile.ticker}
                type="button"
                aria-label={`${tile.ticker}, ${tile.name}, ${formatPercent(tile.ret)} over ${periodWords}`}
                onClick={() => onOpen(tile.ticker)}
                onMouseMove={(event) => {
                  const rect = box.current!.getBoundingClientRect();
                  setTip({ leaf: tile, x: event.clientX - rect.left, y: event.clientY - rect.top });
                }}
                className="absolute overflow-hidden rounded-[4px] p-1 text-left text-xs font-semibold leading-4 transition-[filter] hover:brightness-110 focus-visible:z-10"
                style={{ background: fill, color: ink, height: h, left: tile.x + GAP / 2, top: tile.y + GAP / 2, width: w }}
              >
                {w >= 38 && h >= 20 && <div className="truncate">{tile.ticker}</div>}
                {w >= 52 && h >= 36 && <div className="num font-medium opacity-90">{formatPercent(tile.ret)}</div>}
              </button>
            );
          })}
        </div>
      ))}
      {tip !== null && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-20 w-52 rounded-lg border bg-popover px-3 py-2 text-xs shadow-[0_4px_16px_rgba(0,0,0,0.16)]"
          style={{ left: Math.min(Math.max(0, tip.x + 14), Math.max(0, size.w - 212)), top: Math.min(tip.y + 14, Math.max(0, size.h - 80)) }}
        >
          <div className="font-semibold">{tip.leaf.ticker} <span className="font-normal text-text-2">{tip.leaf.name}</span></div>
          <div className="mt-1 flex justify-between"><span className="text-text-2">Return, {periodWords}</span><span className="num font-medium">{formatPercent(tip.leaf.ret)}</span></div>
          <div className="flex justify-between"><span className="text-text-2">Traded, 20 days</span><span className="num font-medium">${formatCompact(tip.leaf.value)}</span></div>
        </div>
      )}
    </div>
  );
}
