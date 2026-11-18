import { describe, expect, it } from "vitest";

import {
  baseRateFor,
  dayTiles,
  edgeRows,
  filterSignals,
  horizonIndex,
  horizonsOf,
  parseSig,
  rateRows,
  rangeForTimeframe,
  selectSignal,
  signalSentence,
  signedSince,
  toSignal,
  toStat,
  type Signal,
  type Stat,
} from "./signals";

const signal = (over: Partial<Signal> = {}): Signal => ({
  assetClass: "stock",
  day: "2026-11-17",
  direction: "up",
  event: "break_up",
  grade: "B",
  held: true,
  id: "AAA|d|break_up|2026-11-17",
  known: "2026-11-17",
  level: 100,
  marginAtr: 0.6,
  name: "Alpha",
  score: 2,
  since: 0.02,
  slug: "aaa",
  stop: 90,
  ticker: "AAA",
  timeframe: "d",
  ...over,
});

const stat = (over: Partial<Stat> = {}): Stat => ({
  assetClass: "all",
  baselineHit: 0.56,
  baselineMean: 0.004,
  edge: 0.002,
  event: "break_up",
  grade: "all",
  heldRate: 0.7,
  hitRate: 0.58,
  horizon: 20,
  maeMedian: -0.04,
  meanReturn: 0.006,
  mfeMedian: 0.07,
  n: 100,
  timeframe: "d",
  ...over,
});

const ALL_HORIZONS = [5, 20, 60].flatMap((horizon) => [stat({ horizon })]);

describe("reading the API's rows", () => {
  it("reads a signal row with its instrument", () => {
    const row = {
      asset_class: "stock", day: "2026-11-09", direction: "up", event: "break_up", grade: "A",
      held_to_date: true, id: "NVDA|w|break_up|2026-11-09", known: "2026-11-14", level: 142.1,
      margin_atr: 0.6, name: "Nvidia", return_to_date: 0.023, score: 4, slug: "nvda", stop: 128.4, ticker: "NVDA", timeframe: "w",
    };

    expect(toSignal(row)).toMatchObject({ assetClass: "stock", held: true, level: 142.1, marginAtr: 0.6, since: 0.023, timeframe: "w" });
  });

  it("reads a base rate row, nulls and all", () => {
    const row = { asset_class: "all", baseline_hit: null, baseline_mean: null, edge: null, event: "break_up", grade: "A", held_rate: 0.5, hit_rate: 0.6, horizon: 5, mae_median: -0.01, mean_return: 0.01, mfe_median: 0.02, n: 12, timeframe: "d" };

    expect(toStat(row)).toMatchObject({ baselineHit: null, edge: null, hitRate: 0.6, n: 12 });
  });
});

describe("signedSince", () => {
  it("is the move itself for an up signal and its mirror for a down one", () => {
    expect(signedSince(signal({ since: 0.05 }))).toBeCloseTo(0.05);
    expect(signedSince(signal({ direction: "down", since: 0.05 }))).toBeCloseTo(-0.05);
  });

  it("is null before the first later bar has a return", () => {
    expect(signedSince(signal({ since: null }))).toBeNull();
  });
});

describe("filterSignals", () => {
  const rows = [
    signal({ id: "1", ticker: "AAA" }),
    signal({ assetClass: "crypto", grade: "A", id: "2", ticker: "BTC-USD" }),
    signal({ event: "fail_up", direction: "down", grade: "C", id: "3", timeframe: "w" }),
    signal({ event: "confirm_down", direction: "down", grade: "A", id: "4", timeframe: "m" }),
  ];
  const ids = (found: Signal[]) => found.map((s) => s.id);

  it("keeps everything for the open filters", () => {
    expect(ids(filterSignals(rows, { assetClass: "all", event: "all", grade: "all", timeframe: "all" }))).toEqual(["1", "2", "3", "4"]);
  });

  it("keeps A and B for the default grade filter", () => {
    expect(ids(filterSignals(rows, { assetClass: "all", event: "all", grade: "ab", timeframe: "all" }))).toEqual(["1", "2", "4"]);
  });

  it("keeps only A for the strictest", () => {
    expect(ids(filterSignals(rows, { assetClass: "all", event: "all", grade: "a", timeframe: "all" }))).toEqual(["2", "4"]);
  });

  it("combines class, timeframe and event", () => {
    expect(ids(filterSignals(rows, { assetClass: "stock", event: "all", grade: "all", timeframe: "w" }))).toEqual(["3"]);
  });

  it("takes both failures for the failures event", () => {
    const more = [...rows, signal({ event: "fail_down", id: "5" })];

    expect(ids(filterSignals(more, { assetClass: "all", event: "fail", grade: "all", timeframe: "all" }))).toEqual(["3", "5"]);
  });
});

describe("dayTiles", () => {
  const rows = [
    signal({ grade: "A", id: "1" }),
    signal({ id: "2", timeframe: "w" }),
    signal({ id: "3", timeframe: "m" }),
    signal({ id: "4", known: "2026-11-16", held: false }),
    signal({ id: "5", known: "2026-08-01", held: false }),
  ];

  it("counts the day, its A grades and its weekly and monthly signals", () => {
    expect(dayTiles(rows, "2026-11-17")).toMatchObject({ day: 3, gradeA: 1, monthly: 1, weekly: 1 });
  });

  it("measures the share whose stop held over the 90 days to the day", () => {
    const tiles = dayTiles(rows, "2026-11-17");

    expect(tiles.heldOf).toBe(4);
    expect(tiles.heldShare).toBeCloseTo(3 / 4);
  });

  it("has no held share when no signal in the window carries one", () => {
    expect(dayTiles([signal({ held: null })], "2026-11-17").heldShare).toBeNull();
  });
});

describe("base rates", () => {
  it("finds each timeframe's horizons in ascending order", () => {
    const stats = [
      stat({ horizon: 60 }), stat({ horizon: 5 }), stat({ horizon: 20 }),
      stat({ horizon: 13, timeframe: "w" }), stat({ horizon: 4, timeframe: "w" }), stat({ horizon: 26, timeframe: "w" }),
      stat({ horizon: 20, assetClass: "stock" }),
    ];

    expect(horizonsOf(stats)).toMatchObject({ d: [5, 20, 60], w: [4, 13, 26] });
  });

  it("picks the short, primary or long horizon of a timeframe", () => {
    const stats = [stat({ horizon: 5 }), stat({ horizon: 20 }), stat({ horizon: 60 })];

    expect([0, 1, 2].map((choice) => horizonIndex(horizonsOf(stats), "d", choice as 0 | 1 | 2))).toEqual([5, 20, 60]);
  });

  it("answers a signal's base rate from its own class, else from all classes when it has under 30", () => {
    const stats = [
      ...ALL_HORIZONS,
      stat({ assetClass: "stock", hitRate: 0.7, n: 50 }),
      stat({ assetClass: "crypto", hitRate: 0.9, n: 3 }),
    ];

    expect(baseRateFor(stats, signal({ assetClass: "stock" }))?.hitRate).toBe(0.7);
    expect(baseRateFor(stats, signal({ assetClass: "crypto" }))?.hitRate).toBe(0.58);
  });

  it("has no base rate for an event the stats lack", () => {
    expect(baseRateFor([], signal())).toBeNull();
  });

  it("lays out one row per event and timeframe for the asset class, grade and horizon", () => {
    const stats = [
      stat({ event: "break_up", horizon: 5 }),
      stat({ event: "break_up", horizon: 20 }),
      stat({ event: "break_up", horizon: 13, timeframe: "w" }),
      stat({ event: "break_up", grade: "A", horizon: 20 }),
      stat({ event: "break_down", horizon: 20 }),
      stat({ assetClass: "crypto", event: "break_up", horizon: 20 }),
    ];

    const rows = rateRows(stats, { assetClass: "all", event: "all", grade: "all", horizon: 1, timeframe: "all" });

    expect(rows.map((row) => [row.event, row.timeframe, row.horizon])).toEqual([
      ["break_up", "d", 20],
      ["break_up", "w", 13],
      ["break_down", "d", 20],
    ]);
  });

  it("lists edge rows for the bars, leaving out a row with no edge", () => {
    const rows = [stat({ edge: 0.01 }), stat({ edge: null, event: "break_down" }), stat({ edge: -0.02, event: "confirm_up" })];

    expect(edgeRows(rows).map((row) => row.edge)).toEqual([0.01, -0.02]);
  });
});

describe("links", () => {
  it("parses a push's sig into its day and event", () => {
    expect(parseSig("2026-11-10.break_up")).toEqual({ day: "2026-11-10", event: "break_up" });
  });

  it("refuses text that is no signal", () => {
    expect(parseSig("nonsense")).toBeNull();
    expect(parseSig("2026-11-10.bogus")).toBeNull();
    expect(parseSig("")).toBeNull();
  });

  it("asks for the range a push's timeframe uses", () => {
    expect([rangeForTimeframe("d"), rangeForTimeframe("w"), rangeForTimeframe("m")]).toEqual(["1Y", "5Y", "Max"]);
  });

  it("selects the signal a sig names on the timeframe", () => {
    const marks = [
      { day: "2026-11-10", event: "break_up" as const, id: "a", timeframe: "d" as const },
      { day: "2026-11-10", event: "break_up" as const, id: "b", timeframe: "w" as const },
    ];

    expect(selectSignal(marks, "w", "2026-11-10.break_up")?.id).toBe("b");
    expect(selectSignal(marks, "m", "2026-11-10.break_up")).toBeNull();
    expect(selectSignal(marks, "d", null)).toBeNull();
  });
});

describe("signalSentence", () => {
  it("states the event, timeframe, level and what proves it wrong", () => {
    const text = signalSentence({ direction: "up", event: "break_up", grade: "A", known: "2026-11-14", level: 142.1, stop: 128.4, timeframe: "w" }, "stock");

    expect(text).toContain("Weekly first higher high");
    expect(text).toContain("graded A");
    expect(text).toContain("142.10");
    expect(text).toContain("Invalid below 128.40");
  });

  it("says above for a down signal's stop", () => {
    const text = signalSentence({ direction: "down", event: "break_down", grade: "B", known: "2026-11-14", level: 100, stop: 110, timeframe: "d" }, "stock");

    expect(text).toContain("Invalid above 110.00");
  });

  it("names a confirmation's single price once", () => {
    const text = signalSentence({ direction: "up", event: "confirm_up", grade: "B", known: "2026-11-14", level: 100, stop: 100, timeframe: "d" }, "stock");

    expect(text).toContain("Level and stop 100.00");
  });
});
