import { useMemo, useState } from "react";

import { Leaders, type Leader } from "../components/Leaders";
import { Treemap, type Leaf } from "../components/Treemap";
import { Card } from "../components/Card";
import { Delta } from "../components/Delta";
import { Segmented } from "../components/Segmented";
import { Spark } from "../components/Spark";
import { Block, EmptyNote, ErrorNote } from "../components/Status";
import { Tile, TileSkeleton } from "../components/Tile";
import { cn } from "../lib/cn";
import { figure, returnOf } from "../lib/figures";
import {

  formatDay,
  formatPrice,
  formatTileValue,
  formatYield,
} from "../lib/format";
import { useReady } from "../lib/ready";
import type { Route } from "../lib/route";
import { useTokens } from "../lib/theme";
import { ASSET_CLASSES, WINDOWS, type Instrument, type Window } from "../lib/types";
import type { Data } from "../lib/useData";

interface ViewProps {
  data: Data;
  route: Route;
  update: (patch: Partial<Route>) => void;
}

const PERIOD_LABEL: Record<Window, string> = {
  "1d": "1D", "1m": "1M", "1w": "1W", "1y": "1Y", "3m": "3M", ytd: "YTD",
};
const PERIOD_WORDS: Record<Window, string> = {
  "1d": "1 day", "1m": "1 month", "1w": "1 week", "1y": "1 year", "3m": "3 months", ytd: "the year to date",
};
const TREEMAP_BOUND: Record<Window, number> = {
  "1d": 0.03, "1m": 0.1, "1w": 0.06, "1y": 0.5, "3m": 0.2, ytd: 0.3,
};
const CLASS_LABEL: Record<string, string> = {
  all: "All", commodity: "Commodities", crypto: "Crypto", etf: "ETFs", fx: "Currencies", index: "Indices", rate: "Rates", stock: "Stocks",
};
const HEADLINES = [
  { label: "S&P 500", ticker: "^GSPC" },
  { label: "Nasdaq 100", ticker: "^NDX" },
  { label: "US 10-year yield", ticker: "^TNX" },
  { label: "Gold", ticker: "GC=F" },
  { label: "Bitcoin", ticker: "BTC-USD" },
] as const;

const lastValue = (item: Instrument): string => {
  const value = item.metrics.last_close;
  if (value == null) return "–";
  return item.quoteType === "yield" ? formatYield(value) : formatTileValue(value, item.assetClass);
};

function Headlines({ items, period, open }: { items: Instrument[]; period: Window; open: (ticker: string) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-5">
      {HEADLINES.map(({ label, ticker }, index) => {
        const item = items.find((candidate) => candidate.ticker === ticker);
        const span = index === 4 ? "col-span-2 md:col-span-1" : "";
        if (item === undefined) return <TileSkeleton key={ticker} />;
        const current = figure(item, period);
        const day = figure(item, "1d");
        return (
          <Tile
            key={ticker}
            className={span}
            label={label}
            value={lastValue(item)}
            valueTitle={item.metrics.last_close == null ? undefined : item.quoteType === "yield" ? formatYield(item.metrics.last_close) : formatPrice(item.metrics.last_close, item.assetClass)}
            delta={<Delta value={current?.value ?? null} text={current?.text ?? null} />}
            context={period === "1d" ? `Close on ${item.lastDay === null ? "–" : formatDay(item.lastDay)}` : <>1D <Delta value={day?.value ?? null} text={day?.text ?? null} /></>}
            spark={item.spark === null ? undefined : <Spark values={item.spark} label={`${label}, last 63 closes`} width={72} />}
            onClick={() => open(ticker)}
          />
        );
      })}
    </div>
  );
}

/** Not investable levels: rates are shown as yields, and the volatility index swamps a ranking. */
const UNRANKED = new Set(["^VIX"]);

const leaders = (items: Instrument[], period: Window): Leader[] => {
  const ranked = items
    .filter((item) => item.assetClass !== "rate" && !UNRANKED.has(item.ticker))
    .map((item) => ({ name: item.name, ret: returnOf(item, period), ticker: item.ticker }))
    .filter((row): row is Leader => row.ret !== null)
    .sort((a, b) => b.ret - a.ret);
  return ranked.length <= 20 ? ranked : [...ranked.slice(0, 10), ...ranked.slice(-10)];
};

const leaves = (items: Instrument[], period: Window): Leaf[] =>
  items.flatMap((item) => {
    const ret = returnOf(item, period);
    const value = item.metrics.traded_value_20d;
    return item.assetClass === "stock" && ret !== null && value != null && value > 0
      ? [{ name: item.name, ret, sector: item.sector, ticker: item.ticker, value }]
      : [];
  });

function RangeBar({ item }: { item: Instrument }) {
  const { high_52w: high, low_52w: low, last_close: last } = item.metrics;
  if (high == null || low == null || last == null || high <= low) return <span className="text-muted-foreground">–</span>;
  const at = Math.min(1, Math.max(0, (last - low) / (high - low)));
  const label = `52-week range ${formatPrice(low, item.assetClass)} to ${formatPrice(high, item.assetClass)}, last at ${Math.round(at * 100)}%`;
  return (
    <svg role="img" aria-label={label} width="96" height="16" viewBox="0 0 96 16" className="block">
      <title>{label}</title>
      <rect x="0" y="7" width="96" height="2" rx="1" fill="var(--axis)" />
      <circle cx={4 + at * 88} cy="8" r="4" fill="var(--primary)" stroke="var(--card)" strokeWidth="2" />
    </svg>
  );
}

type SortKey = "ticker" | "name" | "last" | Window;

const SORT_VALUE: Record<string, (item: Instrument) => number | string | null> = {
  last: (item) => item.metrics.last_close ?? null,
  name: (item) => item.name,
  ticker: (item) => item.ticker,
  ...Object.fromEntries(WINDOWS.map((w) => [w, (item: Instrument) => figure(item, w)?.value ?? null])),
};

const PAGE_SIZE = 100;

const CLASS_ORDER = Object.fromEntries(ASSET_CLASSES.map((c, i) => [c, i]));

function PageButton({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="h-7 rounded-md border border-input px-2.5 font-medium text-foreground transition-colors hover:bg-muted disabled:text-muted-foreground disabled:opacity-50 disabled:hover:bg-transparent"
    >
      {label}
    </button>
  );
}

function InstrumentTable({ items, route, update, open }: { items: Instrument[]; route: Route; update: (patch: Partial<Route>) => void; open: (ticker: string) => void }) {
  const rows = useMemo(() => {
    const kept = items.filter((item) => route.assetClass === "all" || item.assetClass === route.assetClass);
    const key = SORT_VALUE[route.sort];
    if (key === undefined) {
      return kept.sort((a, b) => (CLASS_ORDER[a.assetClass] ?? 9) - (CLASS_ORDER[b.assetClass] ?? 9) || a.ticker.localeCompare(b.ticker));
    }
    const sign = route.dir === "asc" ? 1 : -1;
    return kept.sort((a, b) => {
      const x = key(a);
      const y = key(b);
      if (x === null) return 1;
      if (y === null) return -1;
      return (typeof x === "string" ? x.localeCompare(y as string) : x - (y as number)) * sign;
    });
  }, [items, route.assetClass, route.sort, route.dir]);

  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const shown = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const sortBy = (key: SortKey): void => {
    const text = key === "ticker" || key === "name";
    update({ dir: route.sort === key ? (route.dir === "asc" ? "desc" : "asc") : text ? "asc" : "desc", sort: key });
  };
  const head = (key: SortKey, label: string, align: "left" | "right", extra = "") => {
    const active = route.sort === key;
    return (
      <th scope="col" aria-sort={active ? (route.dir === "asc" ? "ascending" : "descending") : "none"} className={cn("sticky top-0 z-10 h-9 whitespace-nowrap bg-muted px-3 font-medium text-muted-foreground", align === "right" ? "text-right" : "text-left", extra)}>
        <button type="button" onClick={() => sortBy(key)} className={cn("inline-flex items-center gap-1 hover:text-foreground", active && "text-foreground")}>
          {label}
          <span aria-hidden="true" className="w-2 text-xs">{active ? (route.dir === "asc" ? "↑" : "↓") : ""}</span>
        </button>
      </th>
    );
  };

  return (
    <>
    <div className="scroll-thin max-h-[614px] overflow-auto rounded-md border">
      <table className="w-full min-w-[780px] sm:min-w-[860px] border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            {head("ticker", "Ticker", "left", "sticky left-0 z-20")}
            {head("name", "Name", "left", "hidden sm:table-cell")}
            {head("last", "Last", "right")}
            {WINDOWS.map((w) => head(w, PERIOD_LABEL[w], "right"))}
            <th scope="col" className="sticky top-0 z-10 h-9 bg-muted px-3 text-left font-medium text-muted-foreground">52-week range</th>
            <th scope="col" className="sticky top-0 z-10 h-9 bg-muted px-3 text-left font-medium text-muted-foreground">3 months</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((item) => (
            <tr key={item.ticker} onClick={() => open(item.ticker)} className="group cursor-pointer hover:bg-muted">
              <td className="sticky left-0 z-[1] h-9 border-t bg-card px-3 font-medium group-hover:bg-muted">
                <a href={`?view=ticker&t=${item.ticker}`} onClick={(e) => { e.preventDefault(); e.stopPropagation(); open(item.ticker); }} className="text-foreground no-underline">
                  {item.ticker}
                </a>
              </td>
              <td className="hidden h-9 max-w-52 truncate border-t px-3 text-text-2 sm:table-cell">{item.name}</td>
              <td className="h-9 border-t px-3 text-right num">{item.metrics.last_close == null ? "–" : item.quoteType === "yield" ? formatYield(item.metrics.last_close) : formatPrice(item.metrics.last_close, item.assetClass)}</td>
              {WINDOWS.map((w) => {
                const f = figure(item, w);
                return (
                  <td key={w} className="h-9 border-t px-3 text-right">
                    <Delta value={f?.value ?? null} text={f?.text ?? null} />
                  </td>
                );
              })}
              <td className="h-9 border-t px-3"><RangeBar item={item} /></td>
              <td className="h-9 border-t px-3">{item.spark === null ? <span className="text-muted-foreground">–</span> : <Spark values={item.spark} label={`${item.ticker}, last 63 closes`} width={72} height={22} />}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <EmptyNote>No instruments in this group.</EmptyNote>}
    </div>
    {pages > 1 && (
      <nav aria-label="Pages of instruments" className="mt-3 flex items-center justify-between gap-3 text-sm text-muted-foreground">
        <span>
          {page * PAGE_SIZE + 1}&ndash;{page * PAGE_SIZE + shown.length} of {rows.length}
        </span>
        <span className="flex gap-2">
          <PageButton label="Previous" disabled={page === 0} onClick={() => setPage(page - 1)} />
          <PageButton label="Next" disabled={page === pages - 1} onClick={() => setPage(page + 1)} />
        </span>
      </nav>
    )}
    </>
  );
}

export function Markets({ data, route, update }: ViewProps) {
  const t = useTokens();
  const items = data.overview.status === "ready" ? data.overview.value : null;
  useReady(data.overview.status !== "loading");

  const open = (ticker: string): void => update({ ticker, view: "ticker" });
  const stocks = useMemo(() => (items === null ? null : leaves(items, route.period)), [items, route.period]);
  const ranking = useMemo(() => (items === null ? null : leaders(items, route.period)), [items, route.period]);
  const lastDay = items === null ? null : items.map((i) => i.lastDay).filter((d): d is string => d !== null).sort().at(-1) ?? null;
  const period = PERIOD_WORDS[route.period];
  const failed = data.overview.status === "error";

  return (
    <div className="space-y-3 sm:space-y-4" data-screen="markets">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-muted-foreground">Period</span>
        <Segmented label="Period" options={WINDOWS} value={route.period} onChange={(period) => update({ period })} format={(w) => PERIOD_LABEL[w]} />
      </div>

      {failed ? (
        <ErrorNote onRetry={data.reload}>Couldn&rsquo;t load the market overview: the API didn&rsquo;t answer. Other screens may still work.</ErrorNote>
      ) : items?.length === 0 ? (
        <Card title="Markets">
          <EmptyNote>No instruments stored yet &mdash; the first nightly writes here.</EmptyNote>
        </Card>
      ) : (
        <>
          {items === null ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
              {HEADLINES.map((h) => <TileSkeleton key={h.ticker} />)}
            </div>
          ) : (
            <Headlines items={items} period={route.period} open={open} />
          )}

          <div className="grid gap-3 sm:gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <Card title={`Stocks by sector, return over ${PERIOD_LABEL[route.period]} (%)`} subtitle="Tile size is 20-day traded value; colour is the return">
              {stocks === null ? <Block height={460} /> : <Treemap leaves={stocks} bound={TREEMAP_BOUND[route.period]} tokens={t} periodWords={period} onOpen={open} />}
            </Card>
            <Card title={`Leaders and laggards, ${PERIOD_LABEL[route.period]} (%)`} subtitle="Ten best and ten worst; rates and the volatility index left out">
              {ranking === null ? <Block height={460} /> : <Leaders rows={ranking} periodWords={period} onOpen={open} />}
            </Card>
          </div>

          <Card
            title="All instruments"
            subtitle={lastDay === null ? "Daily bars" : `Prices to ${formatDay(lastDay)}; last is in each instrument's own quote unit (US dollars unless an index, rate or currency pair), and yields move in basis points`}
            actions={<Segmented label="Asset class" options={["all", ...ASSET_CLASSES]} value={route.assetClass as "all"} onChange={(assetClass) => update({ assetClass })} format={(c) => CLASS_LABEL[c] ?? c} />}
          >
            {items === null ? <Block height={420} /> : <InstrumentTable key={`${route.assetClass}|${route.sort}|${route.dir}`} items={items} route={route} update={update} open={open} />}
          </Card>
        </>
      )}
    </div>
  );
}

