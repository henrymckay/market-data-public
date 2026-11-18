/** Signals, base rates and the links that open them: pure functions over the API's rows. */

import { formatDay, formatFixed, formatPercent, formatPrice } from "./format";
import type { Range } from "./stats";

type Row = Record<string, unknown>;

export const TIMEFRAMES = ["d", "w", "m"] as const;
export type Timeframe = (typeof TIMEFRAMES)[number];

export const TIMEFRAME_WORDS: Record<Timeframe, string> = { d: "Daily", m: "Monthly", w: "Weekly" };

/** What one bar of a timeframe is called. */
export const BAR_WORDS: Record<Timeframe, string> = { d: "day", m: "month", w: "week" };

export const EVENTS =["break_up", "confirm_up", "break_down", "confirm_down", "fail_up", "fail_down"] as const;
export type EventName = (typeof EVENTS)[number];

/** The owner's words for each event: the first higher high, the first higher low, and their mirrors. */
export const EVENT_WORDS: Record<EventName, string> = {
  break_down: "First lower low",
  break_up: "First higher high",
  confirm_down: "First lower high",
  confirm_up: "First higher low",
  fail_down: "Lower low failed",
  fail_up: "Higher high failed",
};

/** The words a chart marker carries: short, so neighbouring bars keep their labels. */
export const EVENT_SHORT: Record<EventName, string> = {
  break_down: "Lower low",
  break_up: "Higher high",
  confirm_down: "Lower high",
  confirm_up: "Higher low",
  fail_down: "Low failed",
  fail_up: "High failed",
};

export const EVENT_FILTERS =["all", "break_up", "confirm_up", "break_down", "confirm_down", "fail"] as const;
export type EventFilter = (typeof EVENT_FILTERS)[number];

export const EVENT_FILTER_WORDS: Record<EventFilter, string> = {
  all: "All",
  break_down: "Lower low",
  break_up: "Higher high",
  confirm_down: "Lower high",
  confirm_up: "Higher low",
  fail: "Failures",
};

export const GRADE_FILTERS = ["a", "ab", "all"] as const;
export type GradeFilter = (typeof GRADE_FILTERS)[number];
export const GRADE_FILTER_WORDS: Record<GradeFilter, string> = { a: "A", ab: "A+B", all: "All" };

export const TIMEFRAME_FILTERS = ["all", "d", "w", "m"] as const;
export type TimeframeFilter = (typeof TIMEFRAME_FILTERS)[number];

/** A base rate with fewer signals than this is shown, but muted: the rules' `base-rate-min-n`. */
export const MIN_SAMPLE = 30;

const HELD_WINDOW_DAYS = 90;

export interface Signal {
  ticker: string;
  name: string;
  assetClass: string;
  slug: string;
  timeframe: Timeframe;
  event: EventName;
  direction: "up" | "down";
  grade: "A" | "B" | "C";
  score: number;
  day: string;
  known: string;
  level: number;
  stop: number;
  marginAtr: number | null;
  /** The price move from the signal bar to the last bar, unsigned. */
  since: number | null;
  held: boolean | null;
  id: string;
}

/** What `/api/bars` carries for one signal of the instrument. */
export interface Mark {
  id: string;
  timeframe: Timeframe;
  event: EventName;
  direction: "up" | "down";
  day: string;
  known: string;
  level: number;
  stop: number;
  grade: "A" | "B" | "C";
  score: number;
  since: number | null;
  held: boolean | null;
}

export interface Stat {
  assetClass: string;
  event: EventName;
  grade: string;
  timeframe: Timeframe;
  horizon: number;
  n: number;
  hitRate: number | null;
  baselineHit: number | null;
  baselineMean: number | null;
  edge: number | null;
  heldRate: number | null;
  maeMedian: number | null;
  mfeMedian: number | null;
  meanReturn: number | null;
}

const num = (value: unknown): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);
const day = (value: unknown): string => (typeof value === "string" ? value.slice(0, 10) : "");
const flag = (value: unknown): boolean | null => (typeof value === "boolean" ? value : null);
const grade = (value: unknown): Signal["grade"] => (value === "A" || value === "B" ? value : "C");
const timeframe = (value: unknown): Timeframe => (value === "w" || value === "m" ? value : "d");
const direction = (value: unknown): "up" | "down" => (value === "down" ? "down" : "up");

export const toSignal = (row: Row): Signal => ({
  assetClass: String(row.asset_class),
  day: day(row.day),
  direction: direction(row.direction),
  event: row.event as EventName,
  grade: grade(row.grade),
  held: flag(row.held_to_date),
  id: String(row.id),
  known: day(row.known),
  level: num(row.level) ?? Number.NaN,
  marginAtr: num(row.margin_atr),
  name: String(row.name),
  score: num(row.score) ?? 0,
  since: num(row.return_to_date),
  slug: String(row.slug),
  stop: num(row.stop) ?? Number.NaN,
  ticker: String(row.ticker),
  timeframe: timeframe(row.timeframe),
});

export const toMark = (row: Row): Mark => ({
  day: day(row.day),
  direction: direction(row.direction),
  event: row.event as EventName,
  grade: grade(row.grade),
  held: flag(row.held_to_date),
  id: String(row.id),
  known: day(row.known),
  level: num(row.level) ?? Number.NaN,
  score: num(row.score) ?? 0,
  since: num(row.return_to_date),
  stop: num(row.stop) ?? Number.NaN,
  timeframe: timeframe(row.timeframe),
});

export const toStat = (row: Row): Stat => ({
  assetClass: String(row.asset_class),
  baselineHit: num(row.baseline_hit),
  baselineMean: num(row.baseline_mean),
  edge: num(row.edge),
  event: row.event as EventName,
  grade: String(row.grade),
  heldRate: num(row.held_rate),
  hitRate: num(row.hit_rate),
  horizon: num(row.horizon) ?? 0,
  maeMedian: num(row.mae_median),
  meanReturn: num(row.mean_return),
  mfeMedian: num(row.mfe_median),
  n: num(row.n) ?? 0,
  timeframe: timeframe(row.timeframe),
});

/** The move since the signal bar, positive when the price went the signal's way. */
export const signedSince = (item: Pick<Signal, "direction" | "since">): number | null =>
  item.since === null ? null : item.direction === "up" ? item.since : -item.since;

export interface Filters {
  assetClass: string;
  timeframe: TimeframeFilter;
  event: EventFilter;
  grade: GradeFilter;
}

export const filterSignals = (rows: readonly Signal[], filters: Filters): Signal[] =>
  rows.filter(
    (row) =>
      (filters.assetClass === "all" || row.assetClass === filters.assetClass) &&
      (filters.timeframe === "all" || row.timeframe === filters.timeframe) &&
      (filters.event === "all" || (filters.event === "fail" ? row.event.startsWith("fail_") : row.event === filters.event)) &&
      (filters.grade === "all" || row.grade === "A" || (filters.grade === "ab" && row.grade === "B")),
  );

const shiftDays = (iso: string, days: number): string => {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
};

export interface DayTiles {
  day: number;
  gradeA: number;
  weekly: number;
  monthly: number;
  /** The share of the last 90 days' signals whose stop has held so far, null when none carries a verdict. */
  heldShare: number | null;
  heldOf: number;
}

/** The four tiles over rows already scoped to the asset class. */
export const dayTiles = (rows: readonly Signal[], chosen: string): DayTiles => {
  if (chosen === "") return { day: 0, gradeA: 0, heldOf: 0, heldShare: null, monthly: 0, weekly: 0 };
  const today = rows.filter((row) => row.known === chosen);
  const since = shiftDays(chosen, -HELD_WINDOW_DAYS);
  const window = rows.filter((row) => row.known > since && row.known <= chosen && row.held !== null);
  const held = window.filter((row) => row.held === true).length;
  return {
    day: today.length,
    gradeA: today.filter((row) => row.grade === "A").length,
    heldOf: window.length,
    heldShare: window.length === 0 ? null : held / window.length,
    monthly: today.filter((row) => row.timeframe === "m").length,
    weekly: today.filter((row) => row.timeframe === "w").length,
  };
};

export type Horizons = Record<Timeframe, number[]>;

/** Each timeframe's horizons, in bars and ascending, as the stats carry them. */
export const horizonsOf = (stats: readonly Stat[]): Horizons => {
  const seen: Record<Timeframe, Set<number>> = { d: new Set(), m: new Set(), w: new Set() };
  for (const row of stats) seen[row.timeframe].add(row.horizon);
  const sorted = (set: Set<number>): number[] => [...set].sort((a, b) => a - b);
  return { d: sorted(seen.d), m: sorted(seen.m), w: sorted(seen.w) };
};

export type HorizonChoice = 0 | 1 | 2;
export const HORIZON_WORDS = ["Short", "Primary", "Long"] as const;

/** The horizon in bars a choice names: the first, the middle (primary) or the last of a timeframe's. */
export const horizonIndex = (horizons: Horizons, frame: Timeframe, choice: HorizonChoice): number | null => {
  const list = horizons[frame];
  if (list.length === 0) return null;
  return list[choice === 0 ? 0 : choice === 1 ? Math.floor(list.length / 2) : list.length - 1] ?? null;
};

export interface RateFilters {
  assetClass: string;
  timeframe: TimeframeFilter;
  event: EventFilter;
  grade: string;
  horizon: HorizonChoice;
}

const EVENT_ORDER = Object.fromEntries(EVENTS.map((name, index) => [name, index]));
const FRAME_ORDER = Object.fromEntries(TIMEFRAMES.map((name, index) => [name, index]));

/** One row per event and timeframe at the chosen horizon, in the order the events are told. */
export const rateRows = (stats: readonly Stat[], filters: RateFilters): Stat[] => {
  const horizons = horizonsOf(stats);
  return stats
    .filter(
      (row) =>
        row.assetClass === filters.assetClass &&
        row.grade === filters.grade &&
        (filters.timeframe === "all" || row.timeframe === filters.timeframe) &&
        (filters.event === "all" || (filters.event === "fail" ? row.event.startsWith("fail_") : row.event === filters.event)) &&
        row.horizon === horizonIndex(horizons, row.timeframe, filters.horizon),
    )
    .sort((a, b) => (EVENT_ORDER[a.event] ?? 9) - (EVENT_ORDER[b.event] ?? 9) || (FRAME_ORDER[a.timeframe] ?? 9) - (FRAME_ORDER[b.timeframe] ?? 9));
};

export const edgeRows = (rows: readonly Stat[]): Stat[] => rows.filter((row) => row.edge !== null);

/** The base rate a signal is read against: its class's at the primary horizon, else all classes'. */
export const baseRateFor = (stats: readonly Stat[], item: Pick<Signal, "assetClass" | "event" | "timeframe">): Stat | null => {
  const horizon = horizonIndex(horizonsOf(stats), item.timeframe, 1);
  const find = (assetClass: string): Stat | undefined =>
    stats.find((row) => row.assetClass === assetClass && row.grade === "all" && row.event === item.event && row.timeframe === item.timeframe && row.horizon === horizon);
  const own = find(item.assetClass);
  if (own !== undefined && own.n >= MIN_SAMPLE) return own;
  return find("all") ?? own ?? null;
};

const SIG = /^(\d{4}-\d{2}-\d{2})\.([a-z_]+)$/;

/** The day and event a push's `sig` names, or null for text that is neither. */
export const parseSig = (text: string): { day: string; event: EventName } | null => {
  const match = SIG.exec(text);
  const event = match?.[2];
  if (match === null || event === undefined || !(EVENTS as readonly string[]).includes(event)) return null;
  return { day: match[1]!, event: event as EventName };
};

/** The range a push's link opens for a timeframe, so the signal is on screen with its context. */
export const rangeForTimeframe = (frame: Timeframe): Range => (frame === "d" ? "1Y" : frame === "w" ? "5Y" : "Max");

/** The signal a `sig` names on the timeframe, or null. */
export const selectSignal = <T extends Pick<Mark, "day" | "event" | "timeframe">>(marks: readonly T[], frame: Timeframe, sig: string | null): T | null => {
  const wanted = sig === null ? null : parseSig(sig);
  if (wanted === null) return null;
  return marks.find((mark) => mark.timeframe === frame && mark.day === wanted.day && mark.event === wanted.event) ?? null;
};

/** The `sig` text that opens a signal. */
export const sigOf = (item: Pick<Mark, "day" | "event">): string => `${item.day}.${item.event}`;

/** The signal in one sentence: what turned, the level and what proves it wrong. */
export const signalSentence = (
  item: Pick<Mark, "direction" | "event" | "grade" | "known" | "level" | "stop" | "timeframe">,
  assetClass: string,
): string => {
  const price = (value: number): string => formatPrice(value, assetClass);
  const lead = `${TIMEFRAME_WORDS[item.timeframe]} ${EVENT_WORDS[item.event].toLowerCase()}, graded ${item.grade}, known ${formatDay(item.known)}.`;
  if (item.level === item.stop) return `${lead} Level and stop ${price(item.level)}.`;
  const away = item.stop / item.level - 1;
  return `${lead} Level ${price(item.level)}. Invalid ${item.direction === "up" ? "below" : "above"} ${price(item.stop)} (${formatPercent(away)}).`;
};

/** A hit rate or share as a whole percentage, or a dash. */
export const share = (value: number | null): string => (value === null ? "–" : `${formatFixed(value * 100, 0)}%`);
