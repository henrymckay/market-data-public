import { describe, expect, it } from "vitest";

import { judge } from "./freshness";
import type { Run } from "./types";

const run = (ended: string, outcome: Run["outcome"], source = "yahoo"): Run => ({
  day: "2026-11-16",
  ended,
  failedItems: 0,
  outcome,
  rejected: 0,
  requests: 0,
  rows: 1,
  source,
  started: ended,
});

const NOW = Date.parse("2026-11-17T10:00:00Z");

describe("judge", () => {
  it("is fresh when the last runs stored within two days", () => {
    const verdict = judge([run("2026-11-17T03:00:00Z", "stored"), run("2026-11-17T03:02:00Z", "stored", "metrics")], NOW);
    expect(verdict.level).toBe("fresh");
    expect(verdict.ageMs).toBe(7 * 3_600_000);
  });
  it("is stale once the last stored yahoo run is over two days old", () => {
    expect(judge([run("2026-11-14T03:00:00Z", "stored")], NOW).level).toBe("stale");
  });
  it("is failed when the last run failed, whatever stored before", () => {
    const verdict = judge([run("2026-11-17T03:00:00Z", "stored"), run("2026-11-17T09:00:00Z", "failed")], NOW);
    expect(verdict.level).toBe("failed");
  });
  it("is partial when the last run was partial", () => {
    expect(judge([run("2026-11-17T03:00:00Z", "partial")], NOW).level).toBe("stale");
    expect(
      judge([run("2026-11-17T03:00:00Z", "stored"), run("2026-11-17T03:02:00Z", "partial", "metrics")], NOW).level,
    ).toBe("partial");
  });
  it("has no verdict without runs", () => {
    expect(judge([], NOW).level).toBe("none");
  });
});
