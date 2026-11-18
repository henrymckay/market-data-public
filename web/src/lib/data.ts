import { toMark, toSignal, toStat, type Mark, type Signal, type Stat } from "./signals";
import { TREND_STATES, type Instrument, type Latest, type Pivot, type Run, type TrendState } from "./types";
import type { Series } from "./stats";

/** How long a request may take before the page calls the API unreachable. */
export const TIMEOUT_MS = 30_000;

type Row = Record<string, unknown>;

const num = (value: unknown): number | null => {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
};

/** The API's date or timestamp text as an ISO day. */
export const isoDay = (value: unknown): string | null => (typeof value === "string" ? value.slice(0, 10) : null);

const apiBase = (): string => {
  const base = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, "") ?? "";
  if (base === "") throw new Error("VITE_API_URL was not set when this page was built");
  return base;
};

const fetchJson = async (path: string, init?: RequestInit, version?: string): Promise<unknown> => {
  const suffix = version === undefined ? "" : `?v=${encodeURIComponent(version)}`;
  const response = await fetch(`${apiBase()}/api/${path}${suffix}`, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
};

const METRIC_COLUMNS = new Set([
  "high_52w", "low_52w", "volatility_1y", "drawdown_max_1y", "traded_value_20d", "last_close",
]);

const trendOf = (value: unknown): TrendState | null =>
  typeof value === "string" && (TREND_STATES as readonly string[]).includes(value) ? (value as TrendState) : null;

export const toInstrument = (row: Row): Instrument => {
  const metrics: Record<string, number | null> = {};
  for (const [key, value] of Object.entries(row)) {
    if (key.startsWith("return_") || key.startsWith("change_") || METRIC_COLUMNS.has(key)) metrics[key] = num(value);
  }
  const spark = row.spark;
  return {
    trend: { d: trendOf(row.trend_d), m: trendOf(row.trend_m), w: trendOf(row.trend_w) },
    assetClass: String(row.asset_class),
    barCount: num(row.bar_count) ?? 0,
    firstDay: isoDay(row.first_day),
    lastDay: isoDay(row.last_day),
    metrics,
    name: String(row.name),
    quoteType: row.quote_type === "yield" ? "yield" : "price",
    rejected: num(row.rejected) ?? 0,
    sector: String(row.sector),
    slug: String(row.slug),
    spark: spark == null ? null : Array.from(spark as ArrayLike<number>),
    ticker: String(row.ticker),
  };
};

export const toRun = (row: Row): Run => ({
  day: isoDay(row.day) ?? "",
  ended: String(row.ended),
  failedItems: num(row.failed_items) ?? 0,
  outcome: row.outcome as Run["outcome"],
  rejected: num(row.rejected) ?? 0,
  requests: num(row.requests) ?? 0,
  rows: num(row.rows) ?? 0,
  source: String(row.source),
  started: String(row.started),
});

const column = (values: unknown, fill: number): Float64Array =>
  Float64Array.from(Array.isArray(values) ? values : [], (value) => num(value) ?? fill);

/** The `/api/bars/{slug}` columns as the typed arrays the charts read. */
export const toSeries = (body: Row): Series => ({
  adj: column(body.adj_close, Number.NaN),
  close: column(body.close, Number.NaN),
  days: (Array.isArray(body.day) ? body.day : []).map((day) => isoDay(day) ?? ""),
  dividend: column(body.dividend, 0),
  high: column(body.high, Number.NaN),
  low: column(body.low, Number.NaN),
  open: column(body.open, Number.NaN),
  split: column(body.split, 0),
  volume: column(body.volume, Number.NaN),
});

/** A weekly or monthly bar table: the daily columns less the dividends and splits, which are zero. */
const toPeriodSeries = (body: unknown): Series => {
  const series = toSeries((body ?? {}) as Row);
  return { ...series, dividend: new Float64Array(series.days.length), split: new Float64Array(series.days.length) };
};

const toPivot = (row: Row): Pivot => ({
  day: isoDay(row.day) ?? "",
  kind: row.kind === "low" ? "low" : "high",
  label: typeof row.label === "string" ? row.label : null,
  price: num(row.price) ?? Number.NaN,
  timeframe: row.timeframe === "w" || row.timeframe === "m" ? row.timeframe : "d",
});

/** One instrument's three timeframes of bars, its swings and its signals. */
export interface Bars extends Series {
  weekly: Series;
  monthly: Series;
  pivots: Pivot[];
  marks: Mark[];
}

/** The `/api/bars/{slug}` body: the daily columns, then the structure on top of them. */
export const toBars = (body: Row): Bars => ({
  ...toSeries(body),
  marks: (Array.isArray(body.signals) ? (body.signals as Row[]) : []).map(toMark),
  monthly: toPeriodSeries(body.monthly),
  pivots: (Array.isArray(body.pivots) ? (body.pivots as Row[]) : []).map(toPivot),
  weekly: toPeriodSeries(body.weekly),
});

export const loadOverview = async (version?: string): Promise<Instrument[]> =>
  ((await fetchJson("overview", undefined, version)) as Row[]).map(toInstrument);

export const loadRuns = async (version?: string): Promise<Run[]> =>
  ((await fetchJson("runs", undefined, version)) as Row[]).map(toRun);

/** The last stored run; read afresh each time, since it is how the page learns of a new version. */
export const loadLatest = async (): Promise<Latest | null> => (await fetchJson("latest", { cache: "no-cache" })) as Latest | null;

const barCache = new Map<string, Promise<Bars>>();

/** One instrument's bars, fetched once per session (and once per run's version). */
export const loadBars = (slug: string, version?: string): Promise<Bars> => {
  const key = `${version ?? ""}/${slug}`;
  let pending = barCache.get(key);
  if (pending === undefined) {
    pending = fetchJson(`bars/${slug}`, undefined, version).then((body) => toBars(body as Row));
    barCache.set(key, pending);
    pending.catch(() => barCache.delete(key));
  }
  return pending;
};

const once = <T>(cache: Map<string, Promise<T>>, key: string, make: () => Promise<T>): Promise<T> => {
  let pending = cache.get(key);
  if (pending === undefined) {
    pending = make();
    cache.set(key, pending);
    pending.catch(() => cache.delete(key));
  }
  return pending;
};

const signalCache = new Map<string, Promise<Signal[]>>();
const statCache = new Map<string, Promise<Stat[]>>();

/** The last 120 days of signals, fetched once per run's version and shared by every screen that reads them. */
export const loadSignals = (version?: string): Promise<Signal[]> =>
  once(signalCache, version ?? "", async () => ((await fetchJson("signals", undefined, version)) as Row[]).map(toSignal));

/** Every base rate, fetched once per run's version. */
export const loadStats = (version?: string): Promise<Stat[]> =>
  once(statCache, version ?? "", async () => ((await fetchJson("stats", undefined, version)) as Row[]).map(toStat));
