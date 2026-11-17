import { readFileSync } from "node:fs";
import { parquetReadObjects } from "hyparquet";
import { describe, expect, it } from "vitest";

import { toInstrument, toRun, toSeries } from "./data";

const read = async (name: string) => {
  const bytes = readFileSync(new URL(`./fixtures/${name}`, import.meta.url));
  const file = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
  return parquetReadObjects({ file });
};

describe("files the export wrote", () => {
  it("reads dates as ISO days and counts as numbers (A9)", async () => {
    const rows = (await read("overview.parquet")).map(toInstrument);
    const aapl = rows.find((row) => row.ticker === "AAPL")!;
    expect(aapl.firstDay).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(typeof aapl.barCount).toBe("number");
    expect(typeof aapl.rejected).toBe("number");
    expect(aapl.spark).toHaveLength(63);
    expect(aapl.slug).toBe("aapl");
  });
  it("keeps an instrument with no bars, with nulls", async () => {
    const rows = (await read("overview.parquet")).map(toInstrument);
    const dead = rows.find((row) => row.ticker === "ZZZBOGUS1")!;
    expect(dead.barCount).toBe(0);
    expect(dead.spark).toBeNull();
    expect(dead.metrics.last_close).toBeNull();
  });
  it("marks a yield as one", async () => {
    const rows = (await read("overview.parquet")).map(toInstrument);
    expect(rows.find((row) => row.ticker === "^TNX")!.quoteType).toBe("yield");
  });
  it("reads bars into aligned arrays", async () => {
    const series = toSeries(await read("bars.parquet"));
    expect(series.days).toHaveLength(40);
    expect(series.adj).toHaveLength(40);
    expect(series.days[0]! < series.days[39]!).toBe(true);
  });
  it("reads runs with ISO moments", async () => {
    const run = toRun((await read("runs.parquet"))[0]!);
    expect(run.ended).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
    expect(typeof run.rows).toBe("number");
  });
});
