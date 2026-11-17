/** Range-dependent figures, computed from bars in the browser. */

export const RANGES = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "Max"] as const;
export type Range = (typeof RANGES)[number];

const TRADING_DAYS = 252;
const DAY_MS = 86_400_000;

export interface Series {
  days: string[];
  open: Float64Array;
  high: Float64Array;
  low: Float64Array;
  close: Float64Array;
  adj: Float64Array;
  volume: Float64Array;
  dividend: Float64Array;
  split: Float64Array;
}

/** An ISO day moved back by whole months, clamped to the month's last day. */
export const shiftMonths = (iso: string, months: number): string => {
  const date = new Date(`${iso}T00:00:00Z`);
  const target = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() - months, 1));
  const lastOfTarget = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(date.getUTCDate(), lastOfTarget));
  return target.toISOString().slice(0, 10);
};

/** The day a range starts, or null for the whole history. */
export const rangeStart = (range: Range, last: string): string | null => {
  switch (range) {
    case "1M":
      return shiftMonths(last, 1);
    case "3M":
      return shiftMonths(last, 3);
    case "6M":
      return shiftMonths(last, 6);
    case "YTD":
      return `${Number(last.slice(0, 4)) - 1}-12-31`;
    case "1Y":
      return shiftMonths(last, 12);
    case "5Y":
      return shiftMonths(last, 60);
    case "Max":
      return null;
  }
};

/** The index of the last day at or before `start`, or 0 when history starts later. */
export const startIndex = (days: readonly string[], start: string | null): number => {
  if (start === null) return 0;
  let low = 0;
  let high = days.length - 1;
  let found = 0;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (days[mid]! <= start) {
      found = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return found;
};

export const totalReturn = (values: ArrayLike<number>, from: number, to = values.length - 1): number =>
  values[to]! / values[from]! - 1;

const daysBetween = (first: string, last: string): number => (Date.parse(last) - Date.parse(first)) / DAY_MS;

/** A total return annualised over the calendar days it spans. */
export const annualise = (total: number, first: string, last: string): number => {
  const span = daysBetween(first, last);
  return span <= 0 ? total : (1 + total) ** (365.25 / span) - 1;
};

export const dailyReturns = (values: ArrayLike<number>, from = 0): Float64Array => {
  const out = new Float64Array(Math.max(0, values.length - from - 1));
  for (let i = from + 1; i < values.length; i += 1) out[i - from - 1] = values[i]! / values[i - 1]! - 1;
  return out;
};

export const mean = (values: ArrayLike<number>): number => {
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) sum += values[i]!;
  return values.length === 0 ? Number.NaN : sum / values.length;
};

/** Annualised volatility: the sample standard deviation of daily returns times √252. */
export const volatility = (returns: ArrayLike<number>): number => {
  if (returns.length < 2) return Number.NaN;
  const centre = mean(returns);
  let squares = 0;
  for (let i = 0; i < returns.length; i += 1) squares += (returns[i]! - centre) ** 2;
  return Math.sqrt(squares / (returns.length - 1)) * Math.sqrt(TRADING_DAYS);
};

/** The fall from the running peak, as a fraction at or below zero, from `from` on. */
export const drawdowns = (values: ArrayLike<number>, from = 0): Float64Array => {
  const out = new Float64Array(values.length - from);
  let peak = -Infinity;
  for (let i = from; i < values.length; i += 1) {
    peak = Math.max(peak, values[i]!);
    out[i - from] = values[i]! / peak - 1;
  }
  return out;
};

export const maxDrawdown = (values: ArrayLike<number>, from = 0): number => {
  const falls = drawdowns(values, from);
  let worst = 0;
  for (let i = 0; i < falls.length; i += 1) worst = Math.min(worst, falls[i]!);
  return worst;
};

/** A simple moving average, NaN until `window` values have arrived. */
export const movingAverage = (values: ArrayLike<number>, window: number): Float64Array => {
  const out = new Float64Array(values.length).fill(Number.NaN);
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i]!;
    if (i >= window) sum -= values[i - window]!;
    if (i >= window - 1) out[i] = sum / window;
  }
  return out;
};

export interface Calendar {
  year: number;
  months: (number | null)[];
  total: number;
}

/**
 * Month-by-month returns of adjusted close, one row per year, newest first.
 * A month's return is its last close over the previous month's; the first
 * month of history measures from the first bar.
 */
export const monthlyReturns = (days: readonly string[], values: ArrayLike<number>): Calendar[] => {
  const lastOfMonth = new Map<string, number>();
  for (let i = 0; i < days.length; i += 1) lastOfMonth.set(days[i]!.slice(0, 7), values[i]!);
  const keys = [...lastOfMonth.keys()];
  const rows = new Map<number, (number | null)[]>();
  let previous = values[0]!;
  const yearEnds = new Map<number, number>();
  const yearStart = new Map<number, number>();
  for (const key of keys) {
    const year = Number(key.slice(0, 4));
    const month = Number(key.slice(5, 7)) - 1;
    const close = lastOfMonth.get(key)!;
    const row = rows.get(year) ?? new Array<number | null>(12).fill(null);
    row[month] = close / previous - 1;
    rows.set(year, row);
    if (!yearStart.has(year)) yearStart.set(year, previous);
    yearEnds.set(year, close);
    previous = close;
  }
  return [...rows.entries()]
    .map(([year, months]) => ({ months, total: yearEnds.get(year)! / yearStart.get(year)! - 1, year }))
    .sort((a, b) => b.year - a.year);
};

export const rebase = (values: ArrayLike<number>, from: number, base = 100): Float64Array => {
  const out = new Float64Array(values.length - from);
  for (let i = from; i < values.length; i += 1) out[i - from] = (values[i]! / values[from]!) * base;
  return out;
};

export const correlation = (a: ArrayLike<number>, b: ArrayLike<number>): number => {
  const ma = mean(a);
  const mb = mean(b);
  let covariance = 0;
  let va = 0;
  let vb = 0;
  for (let i = 0; i < a.length; i += 1) {
    covariance += (a[i]! - ma) * (b[i]! - mb);
    va += (a[i]! - ma) ** 2;
    vb += (b[i]! - mb) ** 2;
  }
  return covariance / Math.sqrt(va * vb);
};

export interface Aligned {
  days: string[];
  values: Float64Array[];
}

/**
 * Each series' adjusted close on the days they all have, from the range's
 * start (taken from the earliest last day) to that last day.
 */
export const alignCommon = (series: readonly Series[], range: Range): Aligned => {
  const last = series.map((s) => s.days[s.days.length - 1]!).sort()[0]!;
  const start = rangeStart(range, last);
  const firstDays = series.map((s) => s.days[0]!).sort();
  const floor = firstDays[firstDays.length - 1]!;
  const from = start === null || start < floor ? floor : start;
  const counts = new Map<string, number>();
  for (const s of series) {
    for (const day of s.days) {
      if (day >= from && day <= last) counts.set(day, (counts.get(day) ?? 0) + 1);
    }
  }
  const days = [...counts.entries()]
    .filter(([, n]) => n === series.length)
    .map(([day]) => day)
    .sort();
  const values = series.map((s) => {
    const index = new Map<string, number>();
    s.days.forEach((day, i) => index.set(day, i));
    return Float64Array.from(days, (day) => s.adj[index.get(day)!]!);
  });
  return { days, values };
};
