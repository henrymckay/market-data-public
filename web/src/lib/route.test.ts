import { describe, expect, it } from "vitest";

import { parseRoute, serializeRoute } from "./route";

describe("route", () => {
  it("defaults to Markets over one day", () => {
    const route = parseRoute("");
    expect([route.view, route.period]).toEqual(["markets", "1d"]);
  });
  it("round-trips a ticker view as a shareable link", () => {
    const text = "?view=ticker&t=AAPL&range=5Y&ma50=1&log=1";
    expect(serializeRoute(parseRoute(text))).toBe(text);
  });
  it("keeps symbols readable in the link", () => {
    expect(serializeRoute(parseRoute("?view=ticker&t=^GSPC&range=1M"))).toBe("?view=ticker&range=1M");
    expect(serializeRoute(parseRoute("?view=ticker&t=EURUSD=X"))).toBe("?view=ticker&t=EURUSD=X");
  });
  it("round-trips a push's link, timeframe and signal included", () => {
    const text = "?view=ticker&t=NVDA&tf=w&range=5Y&sig=2026-11-10.break_up";
    expect(parseRoute(text)).toMatchObject({ sig: "2026-11-10.break_up", tf: "w", ticker: "NVDA", view: "ticker" });
    expect(serializeRoute(parseRoute(text))).toBe(text);
  });
  it("opens the Signals screen from a digest's link", () => {
    const route = parseRoute("?view=signals&cls=stock&day=2026-11-17");
    expect([route.view, route.assetClass, route.day, route.grade, route.event, route.tf]).toEqual(["signals", "stock", "2026-11-17", "ab", "all", "all"]);
    expect(serializeRoute(route)).toBe("?view=signals&cls=stock&day=2026-11-17");
  });
  it("keeps every Signals filter in the link and drops the defaults", () => {
    const text = "?view=signals&cls=crypto&tf=w&ev=fail&grade=a";
    expect(serializeRoute(parseRoute(text))).toBe(text);
    expect(serializeRoute(parseRoute("?view=signals&grade=ab&ev=all&tf=all"))).toBe("?view=signals");
  });
  it("leaves the daily timeframe out of a Ticker link", () => {
    expect(serializeRoute(parseRoute("?view=ticker&t=AAPL&tf=d"))).toBe("?view=ticker&t=AAPL");
  });
  it("ignores unknown values", () => {
    const route = parseRoute("?view=nope&period=9y&range=bad&tf=x&ev=y&grade=z&day=soon");
    expect([route.view, route.period, route.range]).toEqual(["markets", "1d", "1Y"]);
    expect([route.tf, route.event, route.grade, route.day]).toEqual(["all", "all", "ab", ""]);
  });
  it("limits the comparison to six instruments", () => {
    expect(parseRoute("?c=A,B,C,D,E,F,G").compare).toHaveLength(6);
  });
});
