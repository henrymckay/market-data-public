import { formatPoints } from "../lib/format";

export interface EdgeRow {
  key: string;
  label: string;
  edge: number;
  title?: string;
}

/** Edge over any bar as bars from a zero line: blue right for a gain, red left for a loss, each labelled. */
export function EdgeBars({ rows, label }: { rows: readonly EdgeRow[]; label: string }) {
  const gain = Math.max(0, ...rows.map((row) => row.edge));
  const loss = Math.max(0, ...rows.map((row) => -row.edge));
  const extent = gain + loss || 1;
  const zero = (loss / extent) * 100;
  return (
    <ul className="m-0 list-none p-0" aria-label={label}>
      {rows.map((row) => {
        const width = (Math.abs(row.edge) / extent) * 100;
        const positive = row.edge >= 0;
        return (
          <li key={row.key} title={row.title} className="grid h-[22px] grid-cols-[132px_minmax(0,1fr)] items-center">
            <span className="truncate pr-2 text-right text-xs font-medium text-text-2">{row.label}</span>
            <span className="relative mx-16 block h-3">
              <span className="absolute inset-y-0 w-px bg-axis" style={{ left: `${zero}%` }} />
              <span
                className="absolute inset-y-0"
                style={{ background: positive ? "var(--up)" : "var(--down)", borderRadius: positive ? "0 4px 4px 0" : "4px 0 0 4px", left: `${positive ? zero : zero - width}%`, width: `${width}%` }}
              />
              <span
                className="num absolute top-1/2 -translate-y-1/2 whitespace-nowrap text-xs"
                style={positive ? { left: `calc(${zero + width}% + 6px)` } : { right: `calc(${100 - zero + width}% + 6px)` }}
              >
                {formatPoints(row.edge)}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
