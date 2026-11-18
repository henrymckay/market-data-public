import { useMemo } from "react";

import { Card } from "../components/Card";
import { EmptyNote, ErrorNote, StatusChip, Block, type Tone } from "../components/Status";
import { Tile, TileSkeleton } from "../components/Tile";
import { formatDay, formatDuration, formatInteger, formatMoment } from "../lib/format";
import { useReady } from "../lib/ready";
import type { Instrument, Run } from "../lib/types";
import type { Data } from "../lib/useData";

const OUTCOME: Record<Run["outcome"], { tone: Tone; label: string }> = {
  failed: { label: "Failed", tone: "critical" },
  partial: { label: "Partial", tone: "warning" },
  stored: { label: "Stored", tone: "good" },
};

const SOURCE_LABEL: Record<string, string> = { metrics: "Metrics", yahoo: "Yahoo prices" };

const coverageTone = (item: Instrument, newest: string | null): { tone: Tone; label: string } => {
  if (item.barCount === 0) return { label: "No bars", tone: "critical" };
  if (newest !== null && item.lastDay !== null && item.lastDay < shiftDays(newest, 4)) return { label: "Behind", tone: "warning" };
  if (item.rejected > 0) return { label: "Rows rejected", tone: "neutral" };
  return { label: "Complete", tone: "good" };
};

const shiftDays = (iso: string, days: number): string => new Date(Date.parse(iso) - days * 86_400_000).toISOString().slice(0, 10);

const HEADS = ["Ended", "Stage", "Outcome", "Rows stored", "Rejected", "Failed", "Requests", "Took"];

export default function Runs({ data }: { data: Data; now: number }) {
  const runs = data.runs.status === "ready" ? data.runs.value : null;
  const items = data.overview.status === "ready" ? data.overview.value : null;
  useReady(data.runs.status !== "loading" && data.overview.status !== "loading");

  const lastYahoo = useMemo(() => runs?.find((run) => run.source === "yahoo") ?? null, [runs]);
  const newest = useMemo(() => items?.map((i) => i.lastDay).filter((d): d is string => d !== null).sort().at(-1) ?? null, [items]);
  const coverage = useMemo(() => {
    if (items === null) return null;
    const rank = (item: Instrument): number => (item.barCount === 0 ? 0 : coverageTone(item, newest).tone === "warning" ? 1 : 2);
    return [...items].sort((a, b) => rank(a) - rank(b) || a.ticker.localeCompare(b.ticker));
  }, [items, newest]);

  const last = runs?.[0] ?? null;
  const verdict = last === null ? null : OUTCOME[last.outcome];

  return (
    <div className="space-y-3 sm:space-y-4" data-screen="runs">
      {data.runs.status === "error" ? (
        <ErrorNote onRetry={data.reload}>Couldn&rsquo;t load the run history: the API didn&rsquo;t answer. Other screens still work.</ErrorNote>
      ) : runs === null ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map((n) => <TileSkeleton key={n} />)}</div>
      ) : last === null || verdict === null ? (
        <EmptyNote>No runs yet — the first nightly writes here.</EmptyNote>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <Tile label="Last run" value={<StatusChip tone={verdict.tone} className="text-2xl font-semibold">{verdict.label}</StatusChip>} context={`${SOURCE_LABEL[last.source] ?? last.source}, ${formatMoment(last.ended)}`} />
            <Tile label="Rows in last price run" value={lastYahoo === null ? "–" : formatInteger(lastYahoo.rows)} context={lastYahoo === null ? "No price run yet" : `Bars stored, prices to ${formatDay(lastYahoo.day)}`} />
            <Tile label="Rows rejected" value={lastYahoo === null ? "–" : formatInteger(lastYahoo.rejected)} context="Quarantined by the last price run" />
            <Tile label="Failed instruments" value={lastYahoo === null ? "–" : formatInteger(lastYahoo.failedItems)} context="Answered nothing usable" />
          </div>

          <Card title="Recent runs" subtitle={`The last ${runs.length} stages, newest first; times in UTC`}>
            <div className="scroll-thin max-h-[398px] overflow-auto rounded-md border">
              <table className="w-full min-w-[760px] border-separate border-spacing-0 text-sm">
                <thead>
                  <tr>
                    {HEADS.map((h, i) => (
                      <th key={h} scope="col" className={`sticky top-0 z-10 h-9 whitespace-nowrap bg-muted px-3 font-medium text-muted-foreground ${i < 3 ? "text-left" : "text-right"}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => {
                    const o = OUTCOME[run.outcome];
                    return (
                      <tr key={`${run.source}${run.ended}`}>
                        <td className="h-9 whitespace-nowrap border-t px-3 num">{formatMoment(run.ended)}</td>
                        <td className="h-9 border-t px-3 text-text-2">{SOURCE_LABEL[run.source] ?? run.source}</td>
                        <td className="h-9 border-t px-3"><StatusChip tone={o.tone}>{o.label}</StatusChip></td>
                        <td className="h-9 border-t px-3 text-right num">{formatInteger(run.rows)}</td>
                        <td className="h-9 border-t px-3 text-right num">{formatInteger(run.rejected)}</td>
                        <td className="h-9 border-t px-3 text-right num">{formatInteger(run.failedItems)}</td>
                        <td className="h-9 border-t px-3 text-right num">{formatInteger(run.requests)}</td>
                        <td className="h-9 border-t px-3 text-right num">{formatDuration(run.started, run.ended)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      <Card title="Coverage by instrument" subtitle="Problems first; a gap or a dead symbol shows here">
        {coverage === null ? (
          data.overview.status === "error" ? <ErrorNote onRetry={data.reload}>Couldn&rsquo;t load the instrument list: the API didn&rsquo;t answer. Other screens still work.</ErrorNote> : <Block height={320} />
        ) : (
          <div className="scroll-thin max-h-[470px] overflow-auto rounded-md border">
            <table className="w-full min-w-[720px] border-separate border-spacing-0 text-sm">
              <thead>
                <tr>
                  {["Ticker", "Name", "First day", "Last day", "Bars", "Rejected", "Status"].map((h, i) => (
                    <th key={h} scope="col" className={`sticky top-0 z-10 h-9 whitespace-nowrap bg-muted px-3 font-medium text-muted-foreground ${i === 4 || i === 5 ? "text-right" : "text-left"}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {coverage.map((item) => {
                  const s = coverageTone(item, newest);
                  return (
                    <tr key={item.ticker}>
                      <td className="h-9 border-t px-3 font-medium">{item.ticker}</td>
                      <td className="h-9 max-w-64 truncate border-t px-3 text-text-2">{item.name}</td>
                      <td className="h-9 whitespace-nowrap border-t px-3 num">{item.firstDay === null ? "–" : formatDay(item.firstDay)}</td>
                      <td className="h-9 whitespace-nowrap border-t px-3 num">{item.lastDay === null ? "–" : formatDay(item.lastDay)}</td>
                      <td className="h-9 border-t px-3 text-right num">{formatInteger(item.barCount)}</td>
                      <td className="h-9 border-t px-3 text-right num">{formatInteger(item.rejected)}</td>
                      <td className="h-9 border-t px-3"><StatusChip tone={s.tone}>{s.label}</StatusChip></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
