import { useEffect, useMemo, useState } from "react";

import { CalendarGrid } from "../components/CalendarGrid";
import { CandleChart } from "../components/CandleChart";
import { Card } from "../components/Card";
import { Chart, frame, tooltipRow, type Option } from "../components/Chart";
import { Delta } from "../components/Delta";
import { Segmented, Toggle } from "../components/Segmented";
import { Block, EmptyNote, ErrorNote } from "../components/Status";
import { Tile } from "../components/Tile";
import { figure } from "../lib/figures";
import {
  formatBasisPoints,
  minus,
  formatDay,
  formatPercent,
  formatPrice,
  formatShare,
  formatYield,
} from "../lib/format";
import { loadBars } from "../lib/data";
import { useReady } from "../lib/ready";
import type { Route } from "../lib/route";
import { drawdowns, maxDrawdown, monthlyReturns, RANGES, rangeStart, startIndex, totalReturn, type Series } from "../lib/stats";
import { useTokens, type Tokens } from "../lib/theme";
import type { Instrument } from "../lib/types";
import type { Data } from "../lib/useData";

interface Props {
  data: Data;
  route: Route;
  update: (patch: Partial<Route>) => void;
  onSearch: () => void;
}

type Bars = { key: string; result: "error" | Series };

const CLASS_NAME: Record<string, string> = {
  commodity: "Commodity future", crypto: "Cryptocurrency", etf: "Exchange-traded fund", fx: "Currency", index: "Index", rate: "Interest rate", stock: "Stock",
};

const UNIT: Record<string, string> = {
  commodity: "US dollars", crypto: "US dollars", etf: "US dollars", fx: "units of the quote currency", index: "index points", rate: "percent", stock: "US dollars",
};

const drawdownOption = (series: Series, from: number, t: Tokens): Option => {
  const falls = drawdowns(series.adj, from);
  const points = series.days.slice(from).map((day, i) => [day, falls[i]!]);
  const base = frame(t);
  return {
    ...base,
    grid: { bottom: 24, left: 48, right: 12, top: 8 },
    series: [{ areaStyle: { color: t.down, opacity: 0.22 }, data: points, itemStyle: { color: t.down }, lineStyle: { color: t.down, width: 1.5 }, sampling: "lttb", showSymbol: false, type: "line" }],
    tooltip: {
      ...base.tooltip,
      formatter: (p: { value: [string, number] }[]) => `<div style="margin-bottom:4px;color:${t.text2}">${formatDay(p[0]!.value[0])}</div>` + tooltipRow(t, "Below peak", formatPercent(p[0]!.value[1])),
      trigger: "axis",
    },
    xAxis: { axisLabel: { color: t.muted, hideOverlap: true }, axisLine: { lineStyle: { color: t.axis } }, axisTick: { show: false }, type: "time" },
    yAxis: { axisLabel: { color: t.muted, formatter: (v: number) => `${minus((v * 100).toFixed(0))}%` }, max: 0, splitLine: { lineStyle: { color: t.grid } }, type: "value" },
  };
};

export default function Ticker({ data, route, update, onSearch }: Props) {
  const t = useTokens();
  const instrument: Instrument | undefined = data.overview.status === "ready" ? data.overview.value.find((i) => i.ticker === route.ticker) : undefined;
  const slug = instrument?.slug;
  const hasBars = instrument !== undefined && instrument.barCount > 0;
  const [loaded, setLoaded] = useState<Bars | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = `${slug}|${data.version}|${attempt}`;

  useEffect(() => {
    if (slug === undefined || !hasBars) return undefined;
    let current = true;
    loadBars(slug, data.version).then(
      (series) => current && setLoaded({ key, result: series }),
      () => current && setLoaded({ key, result: "error" }),
    );
    return () => {
      current = false;
    };
  }, [slug, hasBars, data.version, key]);

  const current = loaded !== null && loaded.key === key ? loaded.result : null;
  const barsFailed = current === "error";
  const series = current === null || current === "error" ? null : current;

  const missing = data.overview.status === "ready" && instrument === undefined;
  const ready = data.overview.status === "error" || missing || (instrument !== undefined && (!hasBars || current !== null));
  useReady(ready);

  const last = series?.days[series.days.length - 1] ?? null;
  const from = series === null || last === null ? 0 : startIndex(series.days, rangeStart(route.range, last));
  const isYield = instrument?.quoteType === "yield";

  const figures = useMemo(() => {
    if (series === null || instrument === undefined) return null;
    const total = totalReturn(series.adj, from);
    return {
      drawdown: maxDrawdown(series.adj, from),
      rangeText: isYield ? formatBasisPoints(series.adj[series.adj.length - 1]! - series.adj[from]!) : formatPercent(total),
      rangeValue: isYield ? series.adj[series.adj.length - 1]! - series.adj[from]! : total,
    };
  }, [series, from, instrument, isYield]);
  const drawdown = useMemo(() => (series === null ? null : drawdownOption(series, from, t)), [series, from, t]);
  const calendar = useMemo(() => (series === null ? null : monthlyReturns(series.days, series.adj)), [series]);

  if (data.overview.status === "error") {
    return <ErrorNote onRetry={data.reload}>Couldn&rsquo;t load the instrument list. Other screens may still work; tonight&rsquo;s run rewrites the file.</ErrorNote>;
  }
  if (missing) {
    return (
      <div className="space-y-3">
        <EmptyNote>No instrument named {route.ticker}. Search for another.</EmptyNote>
        <button type="button" onClick={onSearch} className="rounded-md border border-input px-3 py-1.5 text-sm font-medium">Search instruments</button>
      </div>
    );
  }

  const day = instrument === undefined ? null : figure(instrument, "1d");
  const m = instrument?.metrics;
  const position = m?.last_close != null && m.high_52w != null && m.low_52w != null && m.high_52w > m.low_52w ? (m.last_close - m.low_52w) / (m.high_52w - m.low_52w) : null;
  const price = (n: number | null | undefined): string => (n == null || instrument === undefined ? "–" : isYield ? formatYield(n) : formatPrice(n, instrument.assetClass));

  return (
    <div className="space-y-3 sm:space-y-4" data-screen="ticker">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        <div className="min-w-0">
          {instrument === undefined ? (
            <div className="skeleton h-7 w-56" />
          ) : (
            <>
              <h1 className="m-0 truncate text-xl font-semibold">{instrument.name} <span className="font-normal text-muted-foreground">{instrument.ticker}</span></h1>
              <p className="m-0 text-sm text-muted-foreground">{CLASS_NAME[instrument.assetClass] ?? instrument.assetClass}{instrument.assetClass === "stock" ? ` · ${instrument.sector}` : ""}</p>
            </>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented label="Range" options={RANGES} value={route.range} onChange={(range) => update({ range })} />
          <Toggle label="MA 50" checked={route.ma50} onChange={(ma50) => update({ ma50 })} />
          <Toggle label="MA 200" checked={route.ma200} onChange={(ma200) => update({ ma200 })} />
          <Toggle label="Log" checked={route.log} onChange={(log) => update({ log })} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-5">
        <Tile label="Last close" value={price(m?.last_close)} delta={<Delta value={day?.value ?? null} text={day?.text ?? null} />} context={instrument?.lastDay == null ? "No bars" : `Close on ${formatDay(instrument.lastDay)}, 1D`} className="col-span-2 md:col-span-1" />
        <Tile label={`${isYield ? "Change" : "Return"}, ${route.range}`} value={<Delta value={figures?.rangeValue ?? null} text={figures?.rangeText ?? null} />} context={series === null ? "" : `From ${formatDay(series.days[from]!)}`} />
        <Tile label="52-week position" value={position === null ? "–" : formatShare(position, 0)} context={m?.low_52w == null || m.high_52w == null ? "" : `${price(m.low_52w)} to ${price(m.high_52w)}`} />
        <Tile label="Volatility, 1Y" value={m?.volatility_1y == null ? "–" : formatShare(m.volatility_1y, 1)} context="Annualised, daily returns" />
        <Tile label={`Max drawdown, ${route.range}`} value={<Delta value={figures?.drawdown ?? null} text={figures === null ? null : formatPercent(figures.drawdown)} />} context="Peak to trough, adjusted" />
      </div>

      <Card title={`${instrument?.name ?? route.ticker}, daily candles`} subtitle={`Split-adjusted prices in ${UNIT[instrument?.assetClass ?? ""] ?? "quoted units"}, volume below; markers show dividends and splits`}>
        {instrument !== undefined && !hasBars ? (
          <EmptyNote>No bars stored for {instrument.ticker} yet.</EmptyNote>
        ) : barsFailed ? (
          <ErrorNote onRetry={() => setAttempt((n) => n + 1)}>Couldn&rsquo;t load {route.ticker}&rsquo;s prices. Other screens still work; tonight&rsquo;s run rewrites the file.</ErrorNote>
        ) : series === null || instrument === undefined ? (
          <Block height={520} />
        ) : (
          <CandleChart series={series} assetClass={instrument.assetClass} tokens={t} range={route.range} ma50={route.ma50} ma200={route.ma200} log={route.log} height={520} label={`Candlestick chart of ${instrument.name}, ${route.range}`} />
        )}
      </Card>

      {hasBars && !barsFailed && (
        <div className="grid gap-3 sm:gap-4 lg:grid-cols-2">
          <Card title={`Drawdown from the peak, ${route.range} (%)`} subtitle="Adjusted close against its running high">
            {drawdown === null ? <Block height={300} /> : <Chart option={drawdown} height={300} label={`Underwater chart of ${instrument?.name}, worst ${figures === null ? "" : formatPercent(figures.drawdown)}`} />}
          </Card>
          <Card title="Monthly returns (%)" subtitle="Adjusted close, whole history, newest year first">
            {calendar === null ? <Block height={300} /> : <CalendarGrid rows={calendar} tokens={t} label={`Monthly returns of ${instrument?.name}`} />}
          </Card>
        </div>
      )}
      <div className="sr-only">{last === null ? "" : `Prices to ${formatDay(last)}`}</div>
    </div>
  );
}
