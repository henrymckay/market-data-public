import { describe, expect, it } from "vitest";

import {
  alignCommon,
  annualise,
  correlation,
  drawdowns,
  maxDrawdown,
  monthlyReturns,
  movingAverage,
  rangeStart,
  rebase,
  type Series,
  shiftMonths,
  startIndex,
  totalReturn,
  volatility,
} from "./stats";

const series = (days: string[], adj: number[]): Series => {
  const f = Float64Array.from(adj);
  const zeros = new Float64Array(adj.length);
  return { adj: f, close: f, days, dividend: zeros, high: f, low: f, open: f, split: zeros, volume: zeros };
};

describe("ranges", () => {
  it("steps back by whole months and clamps to the month's end", () => {
    expect(shiftMonths("2026-03-31", 1)).toBe("2026-02-28");
    expect(shiftMonths("2026-11-16", 12)).toBe("2025-11-16");
  });
  it("starts YTD at the end of last year and Max at the beginning", () => {
    expect(rangeStart("YTD", "2026-11-16")).toBe("2025-12-31");
    expect(rangeStart("Max", "2026-11-16")).toBeNull();
  });
  it("starts at the last bar at or before the start day", () => {
    const days = ["2026-01-02", "2026-01-05", "2026-01-06"];
    expect(startIndex(days, "2026-01-04")).toBe(0);
    expect(startIndex(days, "2026-01-05")).toBe(1);
    expect(startIndex(days, "2025-01-01")).toBe(0);
    expect(startIndex(days, null)).toBe(0);
  });
});

describe("returns", () => {
  it("measures the return and annualises it over calendar days", () => {
    expect(totalReturn([100, 110, 121], 0)).toBeCloseTo(0.21, 12);
    expect(annualise(0.21, "2024-01-01", "2026-01-01")).toBeCloseTo(0.1, 2);
  });
});

describe("drawdown", () => {
  it("falls from the running peak", () => {
    const falls = drawdowns([100, 120, 90, 110]);
    expect(Array.from(falls)).toEqual([0, 0, -0.25, 110 / 120 - 1]);
    expect(maxDrawdown([100, 120, 90, 110])).toBe(-0.25);
  });
  it("starts the peak at the range's first bar", () => {
    expect(maxDrawdown([200, 100, 120, 90], 1)).toBeCloseTo(-0.25, 12);
  });
});

describe("volatility", () => {
  it("is the sample deviation of daily returns times root 252", () => {
    const returns = [0.01, -0.01, 0.01, -0.01];
    const sd = Math.sqrt(4 * 0.0001 / 3);
    expect(volatility(returns)).toBeCloseTo(sd * Math.sqrt(252), 12);
  });
});

describe("moving average", () => {
  it("is empty until the window fills", () => {
    const out = movingAverage([1, 2, 3, 4], 3);
    expect(Number.isNaN(out[1]!)).toBe(true);
    expect(Array.from(out.slice(2))).toEqual([2, 3]);
  });
});

describe("monthly returns", () => {
  it("compares each month's last close with the month before, newest year first", () => {
    const days = ["2025-12-31", "2026-01-30", "2026-02-27", "2026-03-31"];
    const rows = monthlyReturns(days, [100, 110, 99, 99]);
    expect(rows.map((row) => row.year)).toEqual([2026, 2025]);
    expect(rows[0]!.months[0]).toBeCloseTo(0.1, 12);
    expect(rows[0]!.months[1]).toBeCloseTo(-0.1, 12);
    expect(rows[0]!.months[2]).toBeCloseTo(0, 12);
    expect(rows[0]!.months[3]).toBeNull();
    expect(rows[0]!.total).toBeCloseTo(-0.01, 12);
  });
});

describe("compare", () => {
  it("rebases to 100 at the first day", () => {
    expect(Array.from(rebase([50, 55, 25], 0))).toEqual([100, expect.closeTo(110, 9), 50]);
  });
  it("aligns on the days every series has, within the range", () => {
    const a = series(["2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"], [1, 2, 3, 4]);
    const b = series(["2026-11-10", "2026-11-12", "2026-11-13"], [10, 30, 40]);
    const aligned = alignCommon([a, b], "Max");
    expect(aligned.days).toEqual(["2026-11-10", "2026-11-12", "2026-11-13"]);
    expect(Array.from(aligned.values[0]!)).toEqual([1, 3, 4]);
  });
  it("correlates perfectly with itself and negatively with its mirror", () => {
    expect(correlation([1, 2, 3, 5], [1, 2, 3, 5])).toBeCloseTo(1, 12);
    expect(correlation([1, 2, 3, 5], [-1, -2, -3, -5])).toBeCloseTo(-1, 12);
  });
});
