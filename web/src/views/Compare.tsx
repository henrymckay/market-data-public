import { Plus, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Card } from "../components/Card";
import { Chart, frame, tooltipRow, type Option } from "../components/Chart";
import { Segmented } from "../components/Segmented";
import { Block, EmptyNote, ErrorNote } from "../components/Status";
import { diverging, inkOn } from "../lib/color";
import { loadBars } from "../lib/data";
import { formatDay, formatFixed, formatPercent } from "../lib/format";
import { useReady } from "../lib/ready";
import { MAX_COMPARE, type Route } from "../lib/route";
import { alignCommon, annualise, correlation, dailyReturns, maxDrawdown, RANGES, rebase, totalReturn, volatility, type Series } from "../lib/stats";
import { useTokens, type Tokens } from "../lib/theme";
import type { Instrument } from "../lib/types";
import type { Data } from "../lib/useData";
import { Delta } from "../components/Delta";

interface Props {
  data: Data;
  route: Route;
  update: (patch: Partial<Route>) => void;
  onSearch: () => void;
}

interface Loaded {
  key: string;
  map: Map<string, Series | "error">;
}

const EMPTY: Instrument[] = [];

/** The palette slot each ticker keeps while it stays in the comparison; a new one takes the lowest free. */
const reconcile = (slots: Map<string, number>, tickers: readonly string[]): Map<string, number> => {
  const next = new Map([...slots].filter(([ticker]) => tickers.includes(ticker)));
  for (const ticker of tickers) {
    if (next.has(ticker)) continue;
    const used = new Set(next.values());
    let slot = 0;
    while (used.has(slot)) slot += 1;
    next.set(ticker, slot);
  }
  const same = next.size === slots.size && [...next].every(([ticker, slot]) => slots.get(ticker) === slot);
  return same ? slots : next;
};

interface Row {
  ticker: string;
  name: string;
  color: string;
  total: number;
  annual: number;
  vol: number;
  ratio: number;
  drawdown: number;
  values: Float64Array;
  returns: Float64Array;
}

const lineOption = (days: string[], rows: Row[], t: Tokens): Option => {
  const base = frame(t);
  return {
    ...base,
    grid: { bottom: 24, left: 44, right: 96, top: 12 },
    series: rows.map((row) => ({
      data: days.map((day, i) => [day, row.values[i]!]),
      emphasis: { focus: "series" },
      endLabel: { color: t.foreground, distance: 6, fontSize: 12, fontWeight: 500, formatter: () => `${row.ticker} ${formatFixed(row.values[row.values.length - 1]!, 0)}`, show: true },
      itemStyle: { color: row.color },
      labelLayout: { moveOverlap: "shiftY" },
      lineStyle: { color: row.color, width: 2 },
      name: row.ticker,
      sampling: "lttb",
      showSymbol: false,
      type: "line",
    })),
    tooltip: {
      ...base.tooltip,
      formatter: (p: { seriesName: string; value: [string, number]; color: string }[]) =>
        `<div style="margin-bottom:4px;color:${t.text2}">${formatDay(p[0]!.value[0])}</div>` +
        [...p].sort((a, b) => b.value[1] - a.value[1]).map((s) => tooltipRow(t, s.seriesName, formatFixed(s.value[1], 1), s.color)).join(""),
      trigger: "axis",
    },
    xAxis: { axisLabel: { color: t.muted, hideOverlap: true }, axisLine: { lineStyle: { color: t.axis } }, axisTick: { show: false }, type: "time" },
    yAxis: { axisLabel: { color: t.muted }, scale: true, splitLine: { lineStyle: { color: t.grid } }, type: "value" },
  };
};

export default function Compare({ data, route, update, onSearch }: Props) {
  const t = useTokens();
  const instruments = data.overview.status === "ready" ? data.overview.value : EMPTY;
  const tickers = route.compare;
  const key = tickers.join(",");
  const [slotState, setSlotState] = useState(() => new Map<string, number>());
  const slots = reconcile(slotState, tickers);
  if (slots !== slotState) setSlotState(slots);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const byTicker = useMemo(() => new Map(instruments.map((i) => [i.ticker, i])), [instruments]);
  const ready = data.overview.status === "ready";
  const pending = !ready || loaded === null || loaded.key !== `${key}|${data.version}`;

  useEffect(() => {
    if (!ready) return undefined;
    let current = true;
    Promise.all(
      key.split(",").filter(Boolean).map(async (ticker): Promise<[string, Series | "error"]> => {
        const item = byTicker.get(ticker);
        if (item === undefined || item.barCount === 0) return [ticker, "error"];
        try {
          return [ticker, await loadBars(item.slug, data.version)];
        } catch {
          return [ticker, "error"];
        }
      }),
    ).then((entries) => {
      if (current) setLoaded({ key: `${key}|${data.version}`, map: new Map(entries) });
    });
    return () => {
      current = false;
    };
  }, [key, byTicker, data.version, ready]);

  useReady(data.overview.status === "error" || (ready && !pending));

  const usableKey = pending ? "" : tickers.filter((ticker) => loaded.map.get(ticker) !== "error").join(",");
  const usable = useMemo(() => usableKey.split(",").filter(Boolean), [usableKey]);
  const failed = pending ? [] : tickers.filter((ticker) => loaded.map.get(ticker) === "error");
  const aligned = useMemo(
    () => (pending || usable.length === 0 ? null : alignCommon(usable.map((ticker) => loaded.map.get(ticker) as Series), route.range)),
    [loaded, pending, usable, route.range],
  );

  const rows: Row[] = useMemo(() => {
    if (aligned === null || aligned.days.length < 3) return [];
    const first = aligned.days[0]!;
    const lastDay = aligned.days[aligned.days.length - 1]!;
    return usable.map((ticker, i) => {
      const adj = aligned.values[i]!;
      const returns = dailyReturns(adj);
      const total = totalReturn(adj, 0);
      const annual = annualise(total, first, lastDay);
      const vol = volatility(returns);
      return {
        annual,
        color: t.series[slots.get(ticker)! % t.series.length]!,
        drawdown: maxDrawdown(adj),
        name: byTicker.get(ticker)?.name ?? ticker,
        ratio: annual / vol,
        returns,
        ticker,
        total,
        values: rebase(adj, 0),
        vol,
      };
    });
  }, [aligned, usable, byTicker, t, slots]);

  if (data.overview.status === "error") {
    return <ErrorNote onRetry={data.reload}>Couldn&rsquo;t load the instrument list. Other screens may still work; tonight&rsquo;s run rewrites the file.</ErrorNote>;
  }

  const option = aligned === null || rows.length === 0 ? null : lineOption(aligned.days, rows, t);
  const remove = (ticker: string): void => update({ compare: tickers.filter((candidate) => candidate !== ticker) });
  const colorOf = (ticker: string): string => t.series[(slots.get(ticker) ?? 0) % t.series.length]!;

  return (
    <div className="space-y-3 sm:space-y-4" data-screen="compare">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        <ul className="m-0 flex list-none flex-wrap items-center gap-2 p-0" aria-label="Instruments compared">
          {tickers.map((ticker) => (
            <li key={ticker} className="flex h-8 items-center gap-2 rounded-md border bg-card pl-2.5 pr-1 text-sm font-medium">
              <span className="size-2.5 rounded-[3px]" style={{ background: colorOf(ticker) }} aria-hidden="true" />
              {ticker}
              <button type="button" onClick={() => remove(ticker)} aria-label={`Remove ${ticker}`} className="grid size-6 place-items-center rounded text-muted-foreground hover:bg-muted hover:text-foreground">
                <X size={14} aria-hidden="true" />
              </button>
            </li>
          ))}
          <li>
            <button type="button" onClick={onSearch} disabled={tickers.length >= MAX_COMPARE} className="flex h-8 items-center gap-1.5 rounded-md border border-dashed border-input px-2.5 text-sm font-medium text-text-2 hover:text-foreground disabled:opacity-50">
              <Plus size={14} aria-hidden="true" />
              {tickers.length >= MAX_COMPARE ? "Six at most" : "Add instrument"}
            </button>
          </li>
        </ul>
        <Segmented label="Range" options={RANGES} value={route.range} onChange={(range) => update({ range })} />
      </div>

      {failed.length > 0 && (
        <ErrorNote>Couldn&rsquo;t load prices for {failed.join(", ")}. The rest are compared; tonight&rsquo;s run rewrites the files.</ErrorNote>
      )}

      {tickers.length === 0 ? (
        <EmptyNote>Pick up to six instruments to compare, with the search above.</EmptyNote>
      ) : (
        <>
          <Card title={`Growth of 100, rebased over ${route.range}`} subtitle={aligned === null || aligned.days.length === 0 ? "Adjusted close, from the first day all have prices" : `Adjusted close, from ${formatDay(aligned.days[0]!)}, the first day all have prices`}>
            {pending || option === null ? (pending ? <Block height={400} /> : <EmptyNote>These instruments share too few days to compare.</EmptyNote>) : <Chart option={option} height={400} label={`Line chart of ${rows.map((r) => r.ticker).join(", ")} rebased to 100`} />}
          </Card>

          <div className="grid gap-3 sm:gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <Card title="Statistics" subtitle="Over the same days; returns from adjusted close">
              {pending ? <Block height={200} /> : rows.length === 0 ? <EmptyNote>Nothing to compare yet.</EmptyNote> : (
                <div className="scroll-thin overflow-x-auto rounded-md border">
                  <table className="w-full min-w-[560px] border-separate border-spacing-0 text-sm">
                    <thead>
                      <tr className="bg-muted text-muted-foreground">
                        {["Instrument", "Total return", "Annualised", "Volatility", "Return / volatility", "Max drawdown"].map((h, i) => (
                          <th key={h} scope="col" className={`h-9 whitespace-nowrap px-3 font-medium ${i === 0 ? "text-left" : "text-right"}`}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.ticker}>
                          <th scope="row" className="h-9 whitespace-nowrap border-t px-3 text-left font-medium">
                            <span className="mr-2 inline-block size-2.5 rounded-[3px]" style={{ background: row.color }} aria-hidden="true" />
                            {row.ticker}
                          </th>
                          <td className="h-9 border-t px-3 text-right"><Delta value={row.total} text={formatPercent(row.total)} /></td>
                          <td className="h-9 border-t px-3 text-right"><Delta value={row.annual} text={formatPercent(row.annual)} /></td>
                          <td className="h-9 border-t px-3 text-right num">{formatFixed(row.vol * 100, 1)}%</td>
                          <td className="h-9 border-t px-3 text-right num">{formatFixed(row.ratio, 2)}</td>
                          <td className="h-9 border-t px-3 text-right"><Delta value={row.drawdown} text={formatPercent(row.drawdown)} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
            <Card title="Correlation of daily returns" subtitle="Same days; 1 moves together, −1 moves opposite">
              {pending ? <Block height={200} /> : rows.length < 2 ? <EmptyNote>Add a second instrument to see how they move together.</EmptyNote> : (
                <div className="scroll-thin overflow-x-auto">
                  <table className="w-full border-separate border-spacing-0.5 text-sm" aria-label="Correlation matrix">
                    <thead>
                      <tr>
                        <td />
                        {rows.map((r) => <th key={r.ticker} scope="col" className="h-8 px-1 text-center text-xs font-medium text-muted-foreground">{r.ticker}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((a) => (
                        <tr key={a.ticker}>
                          <th scope="row" className="pr-2 text-left text-xs font-medium text-muted-foreground">{a.ticker}</th>
                          {rows.map((b) => {
                            const value = a === b ? 1 : correlation(a.returns, b.returns);
                            const fill = diverging(value, 1, t);
                            return (
                              <td key={b.ticker} className="h-9 rounded-[4px] text-center text-sm num" style={{ background: fill, color: inkOn(fill, "#ffffff", "#000000") }}>
                                {formatFixed(value, 2)}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
