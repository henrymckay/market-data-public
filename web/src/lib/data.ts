import { parquetReadObjects } from "hyparquet";

import type { Instrument, Latest, Run } from "./types";
import type { Series } from "./stats";

const base = `${import.meta.env.BASE_URL}data/`;

type Row = Record<string, unknown>;

const num = (value: unknown): number | null => {
  if (value === null || value === undefined) return null;
  const n = typeof value === "bigint" ? Number(value) : (value as number);
  return Number.isFinite(n) ? n : null;
};

/** A parquet date or timestamp as an ISO day (A9: hyparquet returns Date objects). */
export const isoDay = (value: unknown): string | null => {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === "string") return value.slice(0, 10);
  if (typeof value === "number" || typeof value === "bigint") return new Date(Number(value)).toISOString().slice(0, 10);
  return null;
};

const isoMoment = (value: unknown): string => {
  if (value instanceof Date) return value.toISOString().replace(/\.\d+Z$/, "Z");
  return String(value);
};

const fetchBuffer = async (name: string, version?: string): Promise<ArrayBuffer> => {
  const suffix = version === undefined ? "" : `?v=${encodeURIComponent(version)}`;
  const response = await fetch(`${base}${name}${suffix}`);
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  return response.arrayBuffer();
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
  ended: isoMoment(row.ended),
  failedItems: num(row.failed_items) ?? 0,
  outcome: row.outcome as Run["outcome"],
  rejected: num(row.rejected) ?? 0,
  requests: num(row.requests) ?? 0,
  rows: num(row.rows) ?? 0,
  source: String(row.source),
  started: isoMoment(row.started),
});

const column = (rows: Row[], name: string): Float64Array =>
  Float64Array.from(rows, (row) => num(row[name]) ?? Number.NaN);

export const toSeries = (rows: Row[]): Series => ({
  adj: column(rows, "adj_close"),
  close: column(rows, "close"),
  days: rows.map((row) => isoDay(row.day) ?? ""),
  dividend: Float64Array.from(rows, (row) => num(row.dividend) ?? 0),
  high: column(rows, "high"),
  low: column(rows, "low"),
  open: column(rows, "open"),
  split: Float64Array.from(rows, (row) => num(row.split) ?? 0),
  volume: column(rows, "volume"),
});

export const loadOverview = async (version?: string): Promise<Instrument[]> =>
  (await parquetReadObjects({ file: await fetchBuffer("overview.parquet", version) })).map(toInstrument);

export const loadRuns = async (version?: string): Promise<Run[]> =>
  (await parquetReadObjects({ file: await fetchBuffer("runs.parquet", version) })).map(toRun);

export const loadLatest = async (): Promise<Latest | null> => {
  const response = await fetch(`${base}latest.json`, { cache: "no-cache" });
  if (!response.ok) throw new Error(`latest.json: HTTP ${response.status}`);
  return (await response.json()) as Latest | null;
};

const barCache = new Map<string, Promise<Series>>();

/** One instrument's bars, fetched once per session (and once per run's version). */
export const loadBars = (slug: string, version?: string): Promise<Series> => {
  const key = `${version ?? ""}/${slug}`;
  let pending = barCache.get(key);
  if (pending === undefined) {
    pending = fetchBuffer(`bars/${slug}.parquet`, version)
      .then((file) => parquetReadObjects({ file }))
      .then(toSeries);
    barCache.set(key, pending);
    pending.catch(() => barCache.delete(key));
  }
  return pending;
};
