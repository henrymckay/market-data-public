import { useMemo, useState } from "react";

import { Card } from "../components/Card";
import { Delta } from "../components/Delta";
import { EdgeBars } from "../components/EdgeBars";
import { Segmented } from "../components/Segmented";
import { EventLabel, GradeChip, HeldMark } from "../components/SignalParts";
import { Block, EmptyNote, ErrorNote } from "../components/Status";
import { Tile, TileSkeleton } from "../components/Tile";
import { formatDay, formatFixed, formatInteger, formatPercent, formatPrice } from "../lib/format";
import { useReady } from "../lib/ready";
import type { Route } from "../lib/route";
import {
  EVENT_FILTER_WORDS,
  EVENT_FILTERS,
  EVENT_WORDS,
  GRADE_FILTER_WORDS,
  GRADE_FILTERS,
  HORIZON_WORDS,
  MIN_SAMPLE,
  TIMEFRAME_FILTERS,
  TIMEFRAME_WORDS,
  baseRateFor,
  dayTiles,
  edgeRows,
  filterSignals,
  rangeForTimeframe,
  rateRows,
  share,
  sigOf,
  signedSince,
  type HorizonChoice,
  type Signal,
  type Stat,
} from "../lib/signals";
import { ASSET_CLASSES } from "../lib/types";
import { useSignals, type Data } from "../lib/useData";
import { cn } from "../lib/cn";

interface Props {
  data: Data;
  route: Route;
  update: (patch: Partial<Route>) => void;
}

const CLASS_LABEL: Record<string, string> = {
  all: "All", commodity: "Commodities", crypto: "Crypto", etf: "ETFs", fx: "Currencies", index: "Indices", rate: "Rates", stock: "Stocks",
};
const CLASS_WORDS: Record<string, string> = {
  all: "all classes", commodity: "commodities", crypto: "crypto", etf: "ETFs", fx: "currencies", index: "indices", rate: "rates", stock: "stocks",
};
const TF_LABEL: Record<string, string> = { all: "All", d: "D", m: "M", w: "W" };
const PAGE_SIZE = 50;
const GRADE_STATS: Record<string, string> = { A: "A", B: "B", C: "C", all: "all" };

const COLUMNS = [
  ["Known", "left", ""],
  ["Ticker", "left", "sticky left-0 z-20"],
  ["Name", "left", "hidden sm:table-cell"],
  ["TF", "left", ""],
  ["Event", "left", ""],
  ["Grade", "left", ""],
  ["Level", "right", ""],
  ["Stop", "right", ""],
  ["Margin, ATR", "right", ""],
  ["Base rate", "right", ""],
  ["Since", "right", ""],
  ["Held", "left", ""],
] as const;

const FOOTNOTE = "All stored history of today’s members: survivorship flatters the long side, and the rules were set on this data.";

function PageButton({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className="h-7 rounded-md border border-input px-2.5 font-medium text-foreground transition-colors hover:bg-muted disabled:text-muted-foreground disabled:opacity-50 disabled:hover:bg-transparent">
      {label}
    </button>
  );
}

function SignalTable({ rows, stats, open }: { rows: Signal[]; stats: Stat[]; open: (item: Signal) => void }) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const shown = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  return (
    <>
      <div className="scroll-thin max-h-[640px] overflow-auto rounded-md border">
        <table className="w-full min-w-[980px] border-separate border-spacing-0 text-sm">
          <thead>
            <tr>
              {COLUMNS.map(([label, align, extra], index) => (
                <th key={`${label}${index}`} scope="col" className={cn("sticky top-0 z-10 h-9 whitespace-nowrap bg-muted px-3 font-medium text-muted-foreground", align === "right" ? "text-right" : "text-left", extra)}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((item) => {
              const base = baseRateFor(stats, item);
              const since = signedSince(item);
              return (
                <tr key={item.id} onClick={() => open(item)} className="group cursor-pointer hover:bg-muted">
                  <td className="h-9 whitespace-nowrap border-t px-3 num">{formatDay(item.known)}</td>
                  <td className="sticky left-0 z-[1] h-9 border-t bg-card px-3 font-medium group-hover:bg-muted">
                    <a href={`?view=ticker&t=${item.ticker}&tf=${item.timeframe}&sig=${sigOf(item)}`} onClick={(event) => { event.preventDefault(); event.stopPropagation(); open(item); }} className="text-foreground no-underline">
                      {item.ticker}
                    </a>
                  </td>
                  <td className="hidden h-9 max-w-44 truncate border-t px-3 text-text-2 sm:table-cell">{item.name}</td>
                  <td className="h-9 border-t px-3" title={TIMEFRAME_WORDS[item.timeframe]}>{item.timeframe.toUpperCase()}</td>
                  <td className="h-9 border-t px-3"><EventLabel event={item.event} direction={item.direction} /></td>
                  <td className="h-9 border-t px-3"><GradeChip grade={item.grade} /></td>
                  <td className="h-9 border-t px-3 text-right num">{formatPrice(item.level, item.assetClass)}</td>
                  <td className="h-9 border-t px-3 text-right num">{formatPrice(item.stop, item.assetClass)}</td>
                  <td className="h-9 border-t px-3 text-right num">{item.marginAtr === null ? "–" : formatFixed(item.marginAtr, 1)}</td>
                  <td className="h-9 border-t px-3 text-right num" title={base === null ? undefined : `${formatInteger(base.n)} signals, any bar ${share(base.baselineHit)}`}>{base === null ? "–" : share(base.hitRate)}</td>
                  <td className="h-9 border-t px-3 text-right"><Delta value={since} text={since === null ? null : formatPercent(since)} /></td>
                  <td className="h-9 border-t px-3"><HeldMark held={item.held} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <nav aria-label="Pages of signals" className="mt-3 flex items-center justify-between gap-3 text-sm text-muted-foreground">
          <span>{page * PAGE_SIZE + 1}&ndash;{page * PAGE_SIZE + shown.length} of {formatInteger(rows.length)}</span>
          <span className="flex gap-2">
            <PageButton label="Previous" disabled={page === 0} onClick={() => setPage(page - 1)} />
            <PageButton label="Next" disabled={page === pages - 1} onClick={() => setPage(page + 1)} />
          </span>
        </nav>
      )}
    </>
  );
}

function RatesTable({ rows }: { rows: Stat[] }) {
  return (
    <div className="scroll-thin overflow-auto rounded-md border">
      <table className="w-full min-w-[640px] border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            {["Event", "TF", "Bars", "n", "Rose", "Any bar", "Edge", "Stop held", "Best", "Worst"].map((label, index) => (
              <th key={label} scope="col" className={cn("h-9 whitespace-nowrap bg-muted px-3 font-medium text-muted-foreground", index < 2 ? "text-left" : "text-right")}>
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.event}|${row.timeframe}`} className={cn(row.n < MIN_SAMPLE && "text-muted-foreground")} title={row.n < MIN_SAMPLE ? `Fewer than ${MIN_SAMPLE} signals: read with care` : undefined}>
              <td className="h-9 whitespace-nowrap border-t px-3">{EVENT_WORDS[row.event]}</td>
              <td className="h-9 border-t px-3">{row.timeframe.toUpperCase()}</td>
              <td className="h-9 border-t px-3 text-right num">{row.horizon}</td>
              <td className="h-9 border-t px-3 text-right num">{formatInteger(row.n)}</td>
              <td className="h-9 border-t px-3 text-right num">{share(row.hitRate)}</td>
              <td className="h-9 border-t px-3 text-right num">{share(row.baselineHit)}</td>
              <td className="h-9 border-t px-3 text-right"><Delta value={row.edge} text={row.edge === null ? null : formatPercent(row.edge)} /></td>
              <td className="h-9 border-t px-3 text-right num">{share(row.heldRate)}</td>
              <td className="h-9 border-t px-3 text-right num">{row.mfeMedian === null ? "–" : formatPercent(row.mfeMedian)}</td>
              <td className="h-9 border-t px-3 text-right num">{row.maeMedian === null ? "–" : formatPercent(row.maeMedian)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Signals({ data, route, update }: Props) {
  const [attempt, setAttempt] = useState(0);
  const loaded = useSignals(data.version, attempt);
  const [horizon, setHorizon] = useState<HorizonChoice>(1);
  const [grade, setGrade] = useState<string>("all");
  useReady(loaded.status !== "loading");

  const signals = loaded.status === "ready" ? loaded.signals : null;
  const stats = loaded.status === "ready" ? loaded.stats : null;
  const days = useMemo(() => (signals === null ? [] : [...new Set(signals.map((item) => item.known))].sort().reverse()), [signals]);
  const chosen = route.day !== "" ? route.day : (days[0] ?? "");
  const scoped = useMemo(() => (signals === null ? [] : signals.filter((item) => route.assetClass === "all" || item.assetClass === route.assetClass)), [signals, route.assetClass]);
  const tiles = useMemo(() => dayTiles(scoped, chosen), [scoped, chosen]);
  const rows = useMemo(
    () => filterSignals(scoped, { assetClass: "all", event: route.event, grade: route.grade, timeframe: route.tf }).filter((item) => item.known <= chosen),
    [scoped, route.event, route.grade, route.tf, chosen],
  );
  const onTheDay = rows.filter((item) => item.known === chosen).length;
  const rates = useMemo(
    () => (stats === null ? [] : rateRows(stats, { assetClass: route.assetClass, event: route.event, grade: GRADE_STATS[grade] ?? "all", horizon, timeframe: route.tf })),
    [stats, route.assetClass, route.event, route.tf, grade, horizon],
  );
  const edges = useMemo(() => edgeRows(rates).map((row) => ({ edge: row.edge!, key: `${row.event}|${row.timeframe}`, label: `${EVENT_WORDS[row.event]} ${row.timeframe.toUpperCase()}`, title: `${EVENT_WORDS[row.event]}, ${TIMEFRAME_WORDS[row.timeframe].toLowerCase()}: ${formatInteger(row.n)} signals` })), [rates]);

  const open = (item: Signal): void =>
    update({ range: rangeForTimeframe(item.timeframe), sig: sigOf(item), ticker: item.ticker, tf: item.timeframe, view: "ticker" });

  const words = CLASS_WORDS[route.assetClass] ?? route.assetClass;

  if (loaded.status === "error") {
    return <ErrorNote onRetry={() => setAttempt((n) => n + 1)}>Couldn&rsquo;t load the signals: the API didn&rsquo;t answer. Other screens still work; try again in a minute.</ErrorNote>;
  }

  return (
    <div className="space-y-3 sm:space-y-4" data-screen="signals">
      <h1 className="sr-only">Signals</h1>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Segmented label="Asset class" options={["all", ...ASSET_CLASSES]} value={route.assetClass as "all"} onChange={(assetClass) => update({ assetClass })} format={(c) => CLASS_LABEL[c] ?? c} />
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          Day
          <select
            value={chosen}
            disabled={days.length === 0}
            onChange={(event) => update({ day: event.target.value === days[0] ? "" : event.target.value })}
            className="h-8 rounded-md border border-input bg-card px-2 text-sm text-foreground num"
          >
            {days.length === 0 && <option value="">–</option>}
            {days.map((day) => <option key={day} value={day}>{formatDay(day)}</option>)}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
        <span className="flex min-w-0 max-w-full items-center gap-2">Timeframe <Segmented label="Timeframe" options={TIMEFRAME_FILTERS} value={route.tf} onChange={(tf) => update({ tf })} format={(t) => TF_LABEL[t] ?? t} /></span>
        <span className="flex min-w-0 max-w-full items-center gap-2">Event <Segmented label="Event" options={EVENT_FILTERS} value={route.event} onChange={(event) => update({ event })} format={(e) => EVENT_FILTER_WORDS[e]} /></span>
        <span className="flex min-w-0 max-w-full items-center gap-2">Grade <Segmented label="Grade" options={GRADE_FILTERS} value={route.grade} onChange={(g) => update({ grade: g })} format={(g) => GRADE_FILTER_WORDS[g]} /></span>
      </div>

      {signals === null ? (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">{[0, 1, 2, 3].map((n) => <TileSkeleton key={n} />)}</div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <Tile label="Signals" value={formatInteger(tiles.day)} context={chosen === "" ? "No day" : `on ${formatDay(chosen)}`} />
          <Tile label="Graded A" value={formatInteger(tiles.gradeA)} context={`of ${formatInteger(tiles.day)} on the day`} />
          <Tile label="Weekly, monthly" value={formatInteger(tiles.weekly + tiles.monthly)} context={`${formatInteger(tiles.weekly)} W, ${formatInteger(tiles.monthly)} M`} />
          <Tile label="Stop held, 90 days" value={tiles.heldShare === null ? "–" : share(tiles.heldShare)} context={`of ${formatInteger(tiles.heldOf)} signals`} />
        </div>
      )}

      <Card title="Recent signals" subtitle="Newest first, then by score; Since is the price move since the signal bar, positive when it went the signal’s way; Base rate is the share that rose at the primary horizon">
        {signals === null || stats === null ? (
          <Block height={420} />
        ) : signals.length === 0 ? (
          <EmptyNote>No signals yet &mdash; the first nightly with the monitor writes here.</EmptyNote>
        ) : (
          <>
            {onTheDay === 0 && <p className="mb-3 text-sm text-muted-foreground">No signals on {formatDay(chosen)} for {words} &mdash; try All or another day. Earlier ones follow.</p>}
            {rows.length === 0 ? (
              <EmptyNote>No signals for {words} on or before {formatDay(chosen)} with these filters.</EmptyNote>
            ) : (
              <SignalTable key={`${route.assetClass}|${route.tf}|${route.event}|${route.grade}|${chosen}`} rows={rows} stats={stats} open={open} />
            )}
          </>
        )}
      </Card>

      <div className="grid gap-3 sm:gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card
          title={`Base rates for ${words}`}
          subtitle="Rose is the share of signals whose price moved their way at the horizon; Any bar is the same over every bar; Edge is the mean return less the any-bar mean"
          actions={
            <span className="flex flex-wrap items-center gap-2">
              <Segmented label="Horizon" options={HORIZON_WORDS} value={HORIZON_WORDS[horizon]} onChange={(word) => setHorizon(HORIZON_WORDS.indexOf(word) as HorizonChoice)} />
              <Segmented label="Base rate grade" options={["all", "A", "B", "C"]} value={grade} onChange={setGrade} format={(g) => (g === "all" ? "All grades" : `Grade ${g}`)} />
            </span>
          }
        >
          {stats === null ? <Block height={300} /> : rates.length === 0 ? <EmptyNote>No base rates yet for {words} with these filters.</EmptyNote> : <RatesTable rows={rates} />}
        </Card>
        <Card title="Edge over any bar (pp)" subtitle="Mean signed return less the any-bar mean, at the chosen horizon">
          {stats === null ? <Block height={300} /> : edges.length === 0 ? <EmptyNote>No edge to draw for these filters.</EmptyNote> : <EdgeBars rows={edges} label={`Edge over any bar for ${words}`} />}
        </Card>
      </div>
      <p className="m-0 text-sm text-muted-foreground">{FOOTNOTE}</p>
    </div>
  );
}
