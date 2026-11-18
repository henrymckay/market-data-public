import type { Instrument, Latest, Run } from "./types";
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

export const toInstrument = (row: Row): Instrument => {
  const metrics: Record<string, number | null> = {};
  for (const [key, value] of Object.entries(row)) {
    if (key.startsWith("return_") || key.startsWith("change_") || METRIC_COLUMNS.has(key)) metrics[key] = num(value);
  }
  const spark = row.spark;
  return {
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

export const loadOverview = async (version?: string): Promise<Instrument[]> =>
  ((await fetchJson("overview", undefined, version)) as Row[]).map(toInstrument);

export const loadRuns = async (version?: string): Promise<Run[]> =>
  ((await fetchJson("runs", undefined, version)) as Row[]).map(toRun);

/** The last stored run; read afresh each time, since it is how the page learns of a new version. */
export const loadLatest = async (): Promise<Latest | null> => (await fetchJson("latest", { cache: "no-cache" })) as Latest | null;

const barCache = new Map<string, Promise<Series>>();

/** One instrument's bars, fetched once per session (and once per run's version). */
export const loadBars = (slug: string, version?: string): Promise<Series> => {
  const key = `${version ?? ""}/${slug}`;
  let pending = barCache.get(key);
  if (pending === undefined) {
    pending = fetchJson(`bars/${slug}`, undefined, version).then((body) => toSeries(body as Row));
    barCache.set(key, pending);
    pending.catch(() => barCache.delete(key));
  }
  return pending;
};
