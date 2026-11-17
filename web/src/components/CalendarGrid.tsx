import { diverging, inkOn } from "../lib/color";
import { formatFixed } from "../lib/format";
import type { Calendar } from "../lib/stats";
import type { Tokens } from "../lib/theme";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const BOUND = 0.08;

/** Monthly returns with years down and months across, one cell per month and a column for the year. */
export function CalendarGrid({ rows, tokens: t, label }: { rows: readonly Calendar[]; tokens: Tokens; label: string }) {
  const cell = (value: number | null, bound: number, key: string) => {
    if (value === null) return <td key={key} className="h-6 border-t px-0" />;
    const fill = diverging(value, bound, t);
    return (
      <td key={key} className="h-6 border-t px-0 text-center text-xs num" style={{ background: fill, color: inkOn(fill, "#ffffff", "#0b0b0b") }}>
        {formatFixed(value * 100, 1)}
      </td>
    );
  };
  return (
    <div className="scroll-thin h-[300px] overflow-auto rounded-md border" role="region" aria-label={label} tabIndex={0}>
      <table className="w-full min-w-[520px] border-separate border-spacing-0 text-xs">
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 top-0 z-20 h-7 w-12 bg-muted px-2 text-left font-medium text-muted-foreground">Year</th>
            {MONTHS.map((m) => (
              <th key={m} scope="col" className="sticky top-0 z-10 h-7 bg-muted px-0 text-center font-medium text-muted-foreground">{m}</th>
            ))}
            <th scope="col" className="sticky top-0 z-10 h-7 w-14 bg-muted px-2 text-center font-medium text-muted-foreground">Year</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.year}>
              <th scope="row" className="sticky left-0 z-[1] h-6 border-t bg-card px-2 text-left font-medium text-text-2">{row.year}</th>
              {row.months.map((value, i) => cell(value, BOUND, `${row.year}-${i}`))}
              {cell(row.total, BOUND * 3, `${row.year}-total`)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
