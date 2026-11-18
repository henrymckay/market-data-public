import { describe, expect, it } from "vitest";

import {
  formatAge,
  formatBasisPoints,
  formatDay,
  formatMoment,
  formatPercent,
  formatPoints,
  formatPrice,
  formatTileValue,
} from "./format";

describe("formatPoints", () => {
  it("signs a difference of shares in percentage points", () => {
    expect([formatPoints(0.012), formatPoints(-0.0251), formatPoints(0.00001)]).toEqual(["+1.2 pp", "−2.5 pp", "0.0 pp"]);
  });
});

describe("formatPercent", () => {
  it("signs a gain and a loss to two places", () => {
    expect(formatPercent(0.0084)).toBe("+0.84%");
    expect(formatPercent(-0.01919)).toBe("−1.92%");
  });
  it("shows a flat day without a sign", () => {
    expect(formatPercent(0.00001)).toBe("0.00%");
  });
  it("shows a tiny loss as flat, not minus zero", () => {
    expect(formatPercent(-0.000001)).toBe("0.00%");
  });
  it("never shows a raw float", () => {
    expect(formatPercent(0.1 + 0.2)).toBe("+30.00%");
  });
});

describe("formatBasisPoints", () => {
  it("converts percentage points to signed basis points", () => {
    expect(formatBasisPoints(0.033)).toBe("+3 bp");
    expect(formatBasisPoints(-0.125)).toBe("−13 bp");
    expect(formatBasisPoints(0)).toBe("0 bp");
  });
});

describe("prices", () => {
  it("uses thousands separators and two places", () => {
    expect(formatPrice(7416.58984, "index")).toBe("7,416.59");
  });
  it("shows currencies to four places and small prices too", () => {
    expect(formatPrice(1.08421, "fx")).toBe("1.0842");
    expect(formatPrice(0.5234, "crypto")).toBe("0.5234");
  });
  it("compacts a tile value from 50,000", () => {
    expect(formatTileValue(91234.5, "crypto")).toBe("91.2K");
    expect(formatTileValue(24310.15, "index")).toBe("24,310.15");
  });
});

describe("dates", () => {
  it("writes a day as 12 Nov 2026", () => {
    expect(formatDay("2026-11-12")).toBe("12 Nov 2026");
  });
  it("writes a moment on the 24-hour clock in UTC", () => {
    expect(formatMoment("2026-11-17T08:42:01Z")).toBe("17 Nov 2026, 08:42 UTC");
  });
  it("writes an age in the largest sensible unit", () => {
    expect(formatAge(7 * 3_600_000)).toBe("7 h ago");
    expect(formatAge(20_000)).toBe("just now");
    expect(formatAge(5 * 86_400_000)).toBe("5 d ago");
  });
});
