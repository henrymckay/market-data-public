export const WINDOWS = ["1d", "1w", "1m", "3m", "ytd", "1y"] as const;
export type Window = (typeof WINDOWS)[number];

export const ASSET_CLASSES = ["index", "etf", "stock", "rate", "fx", "commodity", "crypto"] as const;
export type AssetClass = (typeof ASSET_CLASSES)[number];

export interface Instrument {
  ticker: string;
  name: string;
  assetClass: string;
  sector: string;
  quoteType: "price" | "yield";
  slug: string;
  metrics: Record<string, number | null>;
  barCount: number;
  firstDay: string | null;
  lastDay: string | null;
  rejected: number;
  spark: number[] | null;
  /** The structure's state per timeframe; null where the instrument has none. */
  trend: { d: TrendState | null; w: TrendState | null; m: TrendState | null };
}

export interface Run {
  day: string;
  ended: string;
  started: string;
  failedItems: number;
  outcome: "stored" | "partial" | "failed";
  rejected: number;
  requests: number;
  rows: number;
  source: string;
}

export interface Latest {
  day: string;
  ended: string;
  outcome: string;
  rows: number;
  /** The end of the last stored metrics or signals run, which the API's cache is keyed on. */
  version?: string | null;
}

/** A swing of one timeframe and how it stands against the one before. */
export interface Pivot {
  timeframe: "d" | "w" | "m";
  kind: "high" | "low";
  label: string | null;
  day: string;
  price: number;
}

/** The structure's state of a market on one timeframe. */
export const TREND_STATES = ["up", "turning_up", "down", "turning_down", "none"] as const;
export type TrendState = (typeof TREND_STATES)[number];
