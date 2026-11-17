import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  PriceScaleMode,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { FONT } from "./Chart";
import { mix } from "../lib/color";
import { formatDay, formatFixed, formatInteger, formatPercent, priceDigits } from "../lib/format";
import { movingAverage, rangeStart, startIndex, type Range, type Series } from "../lib/stats";
import type { Tokens } from "../lib/theme";

interface CandleChartProps {
  series: Series;
  assetClass: string;
  tokens: Tokens;
  range: Range;
  ma50: boolean;
  ma200: boolean;
  log: boolean;
  height: number;
  label: string;
}

const hasVolume = (series: Series): boolean => series.volume.some((v) => v > 0);

const layout = (t: Tokens) => ({
  grid: { horzLines: { color: t.grid }, vertLines: { color: t.grid } },
  layout: { panes: { separatorColor: t.grid, separatorHoverColor: t.axis }, background: { color: t.surface, type: ColorType.Solid }, fontFamily: FONT, fontSize: 12, textColor: t.muted },
  rightPriceScale: { borderColor: t.grid },
  timeScale: { borderColor: t.grid },
});

/** Candles with volume in a second pane, moving averages, a log scale and a crosshair legend. */
export function CandleChart({ series, assetClass, tokens: t, range, ma50, ma200, log, height, label }: CandleChartProps) {
  const element = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volume = useRef<ISeriesApi<"Histogram"> | null>(null);
  const lines = useRef<{ fifty: ISeriesApi<"Line">; two: ISeriesApi<"Line"> } | null>(null);
  const markers = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const tokens = useRef(t);
  useEffect(() => {
    tokens.current = t;
  }, [t]);
  const withVolume = useMemo(() => hasVolume(series), [series]);
  const digits = priceDigits(series.close[series.close.length - 1] ?? 1, assetClass);
  const indexOf = useMemo(() => new Map(series.days.map((day, i) => [day, i])), [series]);

  useEffect(() => {
    const instance = createChart(element.current!, {
      ...layout(tokens.current),
      autoSize: true,
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { borderColor: tokens.current.grid, rightOffset: 3 },
    });
    const body = instance.addSeries(CandlestickSeries, { borderVisible: false, priceLineVisible: false });
    const fifty = instance.addSeries(LineSeries, { crosshairMarkerVisible: false, lastValueVisible: false, lineWidth: 2, priceLineVisible: false, visible: false });
    const two = instance.addSeries(LineSeries, { crosshairMarkerVisible: false, lastValueVisible: false, lineWidth: 2, priceLineVisible: false, visible: false });
    chart.current = instance;
    candles.current = body;
    lines.current = { fifty, two };
    markers.current = createSeriesMarkers(body, []);
    return () => {
      instance.remove();
      chart.current = null;
      candles.current = null;
      volume.current = null;
      lines.current = null;
      markers.current = null;
    };
  }, []);

  useEffect(() => {
    const instance = chart.current!;
    const handler = (event: MouseEventParams<Time>): void => {
      const time = event.time;
      setHover(typeof time === "string" ? (indexOf.get(time) ?? null) : null);
    };
    instance.subscribeCrosshairMove(handler);
    return () => instance.unsubscribeCrosshairMove(handler);
  }, [indexOf]);

  useEffect(() => {
    const instance = chart.current!;
    const body = candles.current!;
    body.setData(series.days.map((time, i) => ({ close: series.close[i]!, high: series.high[i]!, low: series.low[i]!, open: series.open[i]!, time })));
    body.applyOptions({ priceFormat: { formatter: (value: number) => formatFixed(value, digits), minMove: 1 / 10 ** digits, type: "custom" } });
    const closes = Array.from(series.close);
    const average = (window: number) =>
      Array.from(movingAverage(closes, window), (value, i) => ({ time: series.days[i]!, value })).filter((point) => !Number.isNaN(point.value));
    lines.current!.fifty.setData(average(50));
    lines.current!.two.setData(average(200));
    const marks: SeriesMarker<Time>[] = [];
    for (let i = 0; i < series.days.length; i += 1) {
      if (series.split[i]! > 0) marks.push({ color: tokens.current.series[1]!, position: "aboveBar", shape: "square", text: "Split", time: series.days[i]! });
      else if (series.dividend[i]! > 0) marks.push({ color: tokens.current.series[2]!, position: "belowBar", shape: "circle", size: 0.6, time: series.days[i]! });
    }
    markers.current!.setMarkers(marks);
    if (withVolume) {
      if (volume.current === null) {
        volume.current = instance.addSeries(HistogramSeries, { lastValueVisible: false, priceFormat: { type: "volume" }, priceLineVisible: false }, 1);
        instance.panes()[1]?.setHeight(110);
      }
    } else if (volume.current !== null) {
      instance.removeSeries(volume.current);
      volume.current = null;
    }
  }, [series, digits, withVolume]);

  useEffect(() => {
    const instance = chart.current!;
    instance.applyOptions(layout(t));
    candles.current!.applyOptions({ downColor: t.down, upColor: t.up, wickDownColor: t.down, wickUpColor: t.up });
    lines.current!.fifty.applyOptions({ color: t.series[1]! });
    lines.current!.two.applyOptions({ color: t.series[6]! });
    volume.current?.setData(
      series.days.map((time, i) => ({
        color: mix(t.surface, series.close[i]! >= series.open[i]! ? t.up : t.down, 0.55),
        time,
        value: Number.isNaN(series.volume[i]!) ? 0 : series.volume[i]!,
      })),
    );
  }, [t, series, withVolume]);

  useEffect(() => {
    lines.current!.fifty.applyOptions({ visible: ma50 });
  }, [ma50]);
  useEffect(() => {
    lines.current!.two.applyOptions({ visible: ma200 });
  }, [ma200]);
  useEffect(() => {
    chart.current!.priceScale("right").applyOptions({ mode: log ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal });
  }, [log]);

  useEffect(() => {
    const last = series.days[series.days.length - 1]!;
    const start = rangeStart(range, last);
    const scale = chart.current!.timeScale();
    if (start === null) scale.fitContent();
    else scale.setVisibleRange({ from: series.days[startIndex(series.days, start)]! as Time, to: last as Time });
  }, [range, series]);

  const at = hover ?? series.days.length - 1;
  const previous = Math.max(0, at - 1);
  const change = series.close[at]! / series.close[previous]! - 1;
  const price = (n: number): string => formatFixed(n, digits);
  const tone = change > 0 ? "text-up-text" : change < 0 ? "text-down-text" : "text-muted-foreground";

  return (
    <div className="flex flex-col" style={{ height }}>
      <div className="mb-1 flex min-h-[40px] flex-wrap content-start items-baseline gap-x-3 gap-y-0.5 text-sm num sm:min-h-5">
        <span className="font-medium">{formatDay(series.days[at]!)}</span>
        <span className="text-muted-foreground">O <span className="text-foreground">{price(series.open[at]!)}</span></span>
        <span className="text-muted-foreground">H <span className="text-foreground">{price(series.high[at]!)}</span></span>
        <span className="text-muted-foreground">L <span className="text-foreground">{price(series.low[at]!)}</span></span>
        <span className="text-muted-foreground">C <span className="text-foreground">{price(series.close[at]!)}</span></span>
        <span className={tone}>{at === 0 ? "" : formatPercent(change)}</span>
        {withVolume && !Number.isNaN(series.volume[at]!) && <span className="text-muted-foreground">Vol <span className="text-foreground">{formatInteger(series.volume[at]!)}</span></span>}
      </div>
      <div ref={element} role="img" aria-label={label} className="min-h-0 flex-1" />
    </div>
  );
}
