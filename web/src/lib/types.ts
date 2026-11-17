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
}
