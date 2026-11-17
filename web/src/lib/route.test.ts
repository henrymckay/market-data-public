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
  it("ignores unknown values", () => {
    const route = parseRoute("?view=nope&period=9y&range=bad");
    expect([route.view, route.period, route.range]).toEqual(["markets", "1d", "1Y"]);
  });
  it("limits the comparison to six instruments", () => {
    expect(parseRoute("?c=A,B,C,D,E,F,G").compare).toHaveLength(6);
  });
});
