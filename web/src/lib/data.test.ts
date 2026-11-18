import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TIMEOUT_MS, loadBars, loadLatest, loadOverview, loadRuns, loadSignals, loadStats, toBars, toInstrument, toRun, toSeries } from "./data";

const OVERVIEW_ROW = {
  asset_class: "stock",
  bar_count: 70,
  first_day: "2026-01-05",
  last_close: 169,
  last_day: "2026-03-15",
  name: "Alpha",
  quote_type: "price",
  rejected: 2,
  return_1d: 0.01,
  return_5y: null,
  sector: "Tech",
  slug: "aaa",
  spark: [1, 2, 3],
  ticker: "AAA",
};

const RUN_ROW = {
  day: "2026-11-16",
  ended: "2026-11-17T02:19:41Z",
  failed_items: 0,
  last_day: "2026-11-16",
  outcome: "stored",
  rejected: 2,
  requests: 90,
  rows: 803114,
  source: "yahoo",
  started: "2026-11-17T02:17:22Z",
};

const BARS = {
  adj_close: [1.5, null, 3],
  close: [1.5, 2, 3],
  day: ["2026-01-05", "2026-01-06", "2026-01-07"],
  dividend: [0, 0.5, null],
  high: [2, 3, 4],
  low: [1, 1, 2],
  open: [1, 2, 3],
  split: [0, 0, 0],
  ticker: "AAA",
  volume: [10, 20, 30],
};

const STRUCTURE = {
  ...BARS,
  monthly: { adj_close: [3], close: [3], day: ["2026-01-01"], high: [4], low: [1], open: [1], volume: [60] },
  pivots: [
    { confirmed: "2026-01-07", day: "2026-01-05", kind: "high", label: null, price: 2, timeframe: "d" },
    { confirmed: "2026-01-12", day: "2026-01-06", kind: "low", label: "HL", price: 1, timeframe: "w" },
  ],
  signals: [
    { day: "2026-01-06", direction: "up", event: "break_up", grade: "A", held_to_date: true, id: "AAA|d|break_up|2026-01-06", known: "2026-01-06", level: 2, return_to_date: 0.5, score: 3, stop: 1, timeframe: "d" },
  ],
  weekly: { adj_close: [3], close: [3], day: ["2026-01-05"], high: [4], low: [1], open: [1], volume: [60] },
};

const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" }, status });

let calls: string[] = [];
const answer = (reply: (url: string) => Response | Promise<Response>) => {
  calls = [];
  vi.stubGlobal("fetch", (input: string | URL) => {
    const url = String(input);
    calls.push(url);
    return Promise.resolve(reply(url));
  });
};

beforeEach(() => {
  vi.stubEnv("VITE_API_URL", "https://api.example.test/");
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("what the API returns", () => {
  it("reads an overview row into an instrument", () => {
    const aaa = toInstrument(OVERVIEW_ROW);
    expect(aaa).toMatchObject({ barCount: 70, firstDay: "2026-01-05", lastDay: "2026-03-15", slug: "aaa", spark: [1, 2, 3] });
    expect(aaa.metrics).toEqual({ last_close: 169, return_1d: 0.01, return_5y: null });
  });
  it("keeps an instrument with no bars, with nulls", () => {
    const dead = toInstrument({ ...OVERVIEW_ROW, bar_count: 0, first_day: null, last_close: null, spark: null });
    expect([dead.barCount, dead.firstDay, dead.spark, dead.metrics.last_close]).toEqual([0, null, null, null]);
  });
  it("marks a yield as one", () => {
    expect(toInstrument({ ...OVERVIEW_ROW, quote_type: "yield" }).quoteType).toBe("yield");
  });
  it("reads a run's counts and moments", () => {
    expect(toRun(RUN_ROW)).toMatchObject({ day: "2026-11-16", ended: "2026-11-17T02:19:41Z", failedItems: 0, rows: 803114 });
  });
  it("reads bars as aligned arrays, a null price as NaN and a null dividend as 0", () => {
    const series = toSeries(BARS);
    expect(series.days).toEqual(BARS.day);
    expect(Number.isNaN(series.adj[1])).toBe(true);
    expect(series.dividend[2]).toBe(0);
    expect(series.volume[2]).toBe(30);
  });
});

describe("the structure on the bars body", () => {
  it("reads weekly and monthly bars as series with no dividends or splits", () => {
    const bars = toBars(STRUCTURE);

    expect(bars.weekly.days).toEqual(["2026-01-05"]);
    expect(bars.monthly.close[0]).toBe(3);
    expect([bars.weekly.dividend[0], bars.weekly.split[0]]).toEqual([0, 0]);
  });
  it("reads swings and signals, a first swing keeping a null label", () => {
    const bars = toBars(STRUCTURE);

    expect(bars.pivots.map((pivot) => [pivot.timeframe, pivot.kind, pivot.label])).toEqual([["d", "high", null], ["w", "low", "HL"]]);
    expect(bars.marks[0]).toMatchObject({ event: "break_up", held: true, level: 2, since: 0.5, stop: 1, timeframe: "d" });
  });
  it("reads a body from before the structure as empty timeframes", () => {
    const bars = toBars(BARS);

    expect([bars.weekly.days, bars.monthly.days, bars.pivots, bars.marks]).toEqual([[], [], [], []]);
  });
  it("reads the trend per timeframe from the overview, unknown states as none known", () => {
    const aaa = toInstrument({ ...OVERVIEW_ROW, trend_d: "up", trend_m: "turning_down", trend_w: "bogus" });

    expect(aaa.trend).toEqual({ d: "up", m: "turning_down", w: null });
  });
});

describe("fetching", () => {
  it("asks the API's origin for the overview, with no stray slash, and reads it", async () => {
    answer(() => json([OVERVIEW_ROW]));
    const rows = await loadOverview();
    expect(calls).toEqual(["https://api.example.test/api/overview"]);
    expect(rows[0]!.ticker).toBe("AAA");
  });
  it("adds the data version to bust the browser's cache", async () => {
    answer(() => json([RUN_ROW]));
    await loadRuns("2026-11-17T02:19:41Z");
    expect(calls).toEqual(["https://api.example.test/api/runs?v=2026-11-17T02%3A19%3A41Z"]);
  });
  it("reads a null latest", async () => {
    answer(() => json(null));
    expect(await loadLatest()).toBeNull();
  });
  it("fetches an instrument's bars once a session and again for a new version", async () => {
    answer(() => json(BARS));
    await loadBars("aaa");
    await loadBars("aaa");
    await loadBars("aaa", "v2");
    expect(calls).toEqual(["https://api.example.test/api/bars/aaa", "https://api.example.test/api/bars/aaa?v=v2"]);
  });
  it("fetches the signals and the base rates once per version and reads them", async () => {
    answer((url) => json(url.includes("/signals") ? [{ asset_class: "stock", day: "2026-11-17", direction: "up", event: "break_up", grade: "A", id: "x", known: "2026-11-17", level: 1, name: "Alpha", score: 3, slug: "aaa", stop: 0.5, ticker: "AAA", timeframe: "d" }] : [{ asset_class: "all", event: "break_up", grade: "all", horizon: 20, n: 9, timeframe: "d" }]));

    const signals = await loadSignals("v1");
    await loadSignals("v1");
    const stats = await loadStats("v1");
    await loadStats("v1");

    expect(calls).toEqual(["https://api.example.test/api/signals?v=v1", "https://api.example.test/api/stats?v=v1"]);
    expect([signals[0]!.ticker, stats[0]!.n]).toEqual(["AAA", 9]);
  });
  it("rejects with the status and the API's own message on a failure", async () => {
    answer(() => json({ code: "store_unavailable", error: "MotherDuck did not answer; try again in a minute." }, 503));
    await expect(loadOverview()).rejects.toThrow("503");
  });
  it("forgets a failed bars fetch so a retry asks again", async () => {
    answer(() => json({ code: "x", error: "x" }, 503));
    await expect(loadBars("bbb")).rejects.toThrow();
    answer(() => json(BARS));
    await expect(loadBars("bbb")).resolves.toBeDefined();
  });
  it("rejects with an instruction when the build had no API address", async () => {
    vi.stubEnv("VITE_API_URL", "");
    answer(() => json([]));
    await expect(loadOverview()).rejects.toThrow("VITE_API_URL");
    expect(calls).toEqual([]);
  });
  it("limits each request to the timeout, so a silent API ends in an error", async () => {
    const timeout = vi.spyOn(AbortSignal, "timeout");
    answer(() => json([]));
    await loadOverview();
    expect(timeout).toHaveBeenCalledWith(TIMEOUT_MS);
    timeout.mockRestore();
  });
});
