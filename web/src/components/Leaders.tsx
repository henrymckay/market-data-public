import { formatPercent } from "../lib/format";

export interface Leader {
  ticker: string;
  name: string;
  ret: number;
}

/** The best and worst as bars from a zero line: blue right for gains, red left for losses, each labelled. */
export function Leaders({ rows, periodWords, onOpen }: { rows: readonly Leader[]; periodWords: string; onOpen: (ticker: string) => void }) {
  const gain = Math.max(0, ...rows.map((r) => r.ret));
  const loss = Math.max(0, ...rows.map((r) => -r.ret));
  const extent = gain + loss || 1;
  const zero = (loss / extent) * 100;
  return (
    <ul className="m-0 list-none p-0" aria-label={`Ten best and ten worst over ${periodWords}`}>
      {rows.map((row) => {
        const width = (Math.abs(row.ret) / extent) * 100;
        const positive = row.ret >= 0;
        return (
          <li key={row.ticker}>
            <button type="button" onClick={() => onOpen(row.ticker)} title={row.name} className="grid h-[22px] w-full grid-cols-[84px_minmax(0,1fr)] items-center rounded-sm text-left hover:bg-muted">
              <span className="truncate pr-2 text-right text-xs font-medium text-text-2">{row.ticker}</span>
              <span className="relative mx-14 block h-3">
                <span className="absolute inset-y-0 w-px bg-axis" style={{ left: `${zero}%` }} />
                <span className="absolute inset-y-0" style={{ background: positive ? "var(--up)" : "var(--down)", borderRadius: positive ? "0 4px 4px 0" : "4px 0 0 4px", left: `${positive ? zero : zero - width}%`, width: `${width}%` }} />
                <span className="num absolute top-1/2 -translate-y-1/2 whitespace-nowrap text-xs" style={positive ? { left: `calc(${zero + width}% + 6px)` } : { right: `calc(${100 - zero + width}% + 6px)` }}>
                  {formatPercent(row.ret)}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
