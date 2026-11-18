import { useEffect, useMemo, useState } from "react";

import { CalendarGrid } from "../components/CalendarGrid";
import { CandleChart } from "../components/CandleChart";
import { EventLabel, GradeChip, HeldMark } from "../components/SignalParts";
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
  formatInteger,
  formatPercent,
  formatPrice,
  formatShare,
  formatYield,
} from "../lib/format";
import { loadBars, type Bars } from "../lib/data";
import { useReady } from "../lib/ready";
import { BAR_WORDS, TIMEFRAMES, TIMEFRAME_WORDS, baseRateFor, selectSignal, share, sigOf, signalSentence, signedSince, type Mark, type Timeframe } from "../lib/signals";
import type { Route } from "../lib/route";
import { drawdowns, maxDrawdown, monthlyReturns, RANGES, rangeStart, startIndex, totalReturn, type Series } from "../lib/stats";
import { useTokens, type Tokens } from "../lib/theme";
import type { Instrument } from "../lib/types";
import { useSignals, type Data } from "../lib/useData";

interface Props {
  data: Data;
  route: Route;
  update: (patch: Partial<Route>) => void;
  onSearch: () => void;
}

type Loaded = { key: string; result: "error" | Bars };

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

const baseRateText = (stats: Parameters<typeof baseRateFor>[0], mark: Mark, assetClass: string): string => {
  const rate = baseRateFor(stats, { assetClass, event: mark.event, timeframe: mark.timeframe });
  if (rate === null) return "";
  return `Base rate: ${share(rate.hitRate)} moved this way within ${rate.horizon} ${BAR_WORDS[mark.timeframe]}s (${formatInteger(rate.n)} ${rate.n === 1 ? "signal" : "signals"}); any bar ${share(rate.baselineHit)}.`;
};

function BaseRate({ text }: { text: string }) {
  return text === "" ? null : <> {text}</>;
}

function SignalList({ marks, assetClass, selected, open }: { marks: Mark[]; assetClass: string; selected: Mark | null; open: (mark: Mark) => void }) {
  return (
    <div className="scroll-thin max-h-[320px] overflow-auto rounded-md border">
      <table className="w-full min-w-[640px] border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            {["Known", "Event", "Grade", "Level", "Stop", "Since", "Held"].map((label, index) => (
              <th key={label} scope="col" className={`sticky top-0 z-10 h-9 whitespace-nowrap bg-muted px-3 font-medium text-muted-foreground ${index === 3 || index === 4 || index === 5 ? "text-right" : "text-left"}`}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {marks.map((mark) => {
            const since = signedSince(mark);
            return (
              <tr key={mark.id} onClick={() => open(mark)} aria-selected={selected?.id === mark.id} className={`cursor-pointer hover:bg-muted ${selected?.id === mark.id ? "bg-muted" : ""}`}>
                <td className="h-9 whitespace-nowrap border-t px-3 num">{formatDay(mark.known)}</td>
                <td className="h-9 border-t px-3"><EventLabel event={mark.event} direction={mark.direction} /></td>
                <td className="h-9 border-t px-3"><GradeChip grade={mark.grade} /></td>
                <td className="h-9 border-t px-3 text-right num">{formatPrice(mark.level, assetClass)}</td>
                <td className="h-9 border-t px-3 text-right num">{formatPrice(mark.stop, assetClass)}</td>
                <td className="h-9 border-t px-3 text-right"><Delta value={since} text={since === null ? null : formatPercent(since)} /></td>
                <td className="h-9 border-t px-3"><HeldMark held={mark.held} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function Ticker({ data, route, update, onSearch }: Props) {
  const t = useTokens();
  const instrument: Instrument | undefined = data.overview.status === "ready" ? data.overview.value.find((i) => i.ticker === route.ticker) : undefined;
  const slug = instrument?.slug;
  const hasBars = instrument !== undefined && instrument.barCount > 0;
  const [loaded, setLoaded] = useState<Loaded | null>(null);
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

  const tf: Timeframe = route.tf === "w" || route.tf === "m" ? route.tf : "d";
  const frame: Series | null = series === null ? null : tf === "d" ? series : tf === "w" ? series.weekly : series.monthly;
  const marks = useMemo(() => (series === null ? [] : series.marks.filter((mark) => mark.timeframe === tf)), [series, tf]);
  const structure = useMemo(
    () => ({ marks, pivots: series === null ? [] : series.pivots.filter((pivot) => pivot.timeframe === tf), selected: selectSignal(marks, tf, route.sig === "" ? null : route.sig), timeframe: tf }),
    [series, marks, tf, route.sig],
  );
  const signalled = useSignals(data.version, 0, structure.selected !== null);
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
    return <ErrorNote onRetry={data.reload}>Couldn&rsquo;t load the instrument list: the API didn&rsquo;t answer. Other screens may still work.</ErrorNote>;
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
          <Segmented label="Timeframe" options={TIMEFRAMES} value={tf} onChange={(next) => update({ sig: "", tf: next })} format={(frameName) => frameName.toUpperCase()} />
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

      {structure.selected !== null && instrument !== undefined && (
        <p role="status" className="m-0 rounded-md border bg-card px-3 py-2 text-sm" data-testid="signal-note">
          <span className="font-medium">{instrument.ticker}.</span> {signalSentence(structure.selected, instrument.assetClass)}
          {signalled.status === "ready" && <BaseRate text={baseRateText(signalled.stats, structure.selected, instrument.assetClass)} />}
        </p>
      )}

      <Card title={`${instrument?.name ?? route.ticker}, ${TIMEFRAME_WORDS[tf].toLowerCase()} candles`} subtitle={`Split-adjusted prices in ${UNIT[instrument?.assetClass ?? ""] ?? "quoted units"}, volume below; arrows are signals, grey labels are swings, small markers are dividends and splits`}>
        {instrument !== undefined && !hasBars ? (
          <EmptyNote>No bars stored for {instrument.ticker} yet.</EmptyNote>
        ) : barsFailed ? (
          <ErrorNote onRetry={() => setAttempt((n) => n + 1)}>Couldn&rsquo;t load {route.ticker}&rsquo;s prices: the API didn&rsquo;t answer. Other screens still work.</ErrorNote>
        ) : frame === null || instrument === undefined ? (
          <Block height={520} />
        ) : frame.days.length === 0 ? (
          <EmptyNote>No {TIMEFRAME_WORDS[tf].toLowerCase()} bars stored for {instrument.ticker} yet.</EmptyNote>
        ) : (
          <CandleChart series={frame} structure={structure} assetClass={instrument.assetClass} tokens={t} range={route.range} ma50={route.ma50} ma200={route.ma200} log={route.log} height={520} label={`Candlestick chart of ${instrument.name}, ${TIMEFRAME_WORDS[tf].toLowerCase()}, ${route.range}`} />
        )}
      </Card>

      {hasBars && !barsFailed && instrument !== undefined && series !== null && (
        <Card title={`Signals, ${TIMEFRAME_WORDS[tf].toLowerCase()}`} subtitle="Newest first; Since is the price move since the signal bar, positive when it went the signal’s way">
          {marks.length === 0 ? (
            <EmptyNote>No {TIMEFRAME_WORDS[tf].toLowerCase()} signals for {instrument.ticker} yet.</EmptyNote>
          ) : (
            <SignalList marks={[...marks].reverse()} assetClass={instrument.assetClass} selected={structure.selected} open={(mark) => update({ sig: sigOf(mark) })} />
          )}
        </Card>
      )}

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
