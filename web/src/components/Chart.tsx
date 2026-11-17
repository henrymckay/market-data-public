import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

import type { Tokens } from "../lib/theme";

echarts.use([LineChart, GridComponent, TooltipComponent, LabelLayout, CanvasRenderer]);

export type Option = echarts.EChartsCoreOption;

export const FONT = "Inter Variable, system-ui, sans-serif";

export const frame = (t: Tokens) => ({
  animation: false,
  textStyle: { color: t.muted, fontFamily: FONT, fontSize: 12 },
  tooltip: {
    backgroundColor: t.raised,
    borderColor: t.border,
    borderWidth: 1,
    extraCssText: "box-shadow: 0 4px 16px rgba(0,0,0,0.16); border-radius: 8px;",
    padding: [8, 12],
    textStyle: { color: t.foreground, fontFamily: FONT, fontSize: 12 },
  },
});

export const tooltipRow = (t: Tokens, name: string, value: string, color?: string): string =>
  `<div style="display:flex;justify-content:space-between;gap:16px;font-variant-numeric:tabular-nums">` +
  `<span style="color:${t.text2}">${color === undefined ? "" : `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${color};margin-right:6px"></span>`}${name}</span>` +
  `<span style="font-weight:500">${value}</span></div>`;

interface ChartProps {
  option: Option;
  height: number;
  label: string;
  onClick?: (data: Record<string, unknown>) => void;
}

/** One ECharts instance that follows its container's size and redraws from a new option. */
export function Chart({ option, height, label, onClick }: ChartProps) {
  const element = useRef<HTMLDivElement>(null);
  const instance = useRef<echarts.ECharts | null>(null);
  const handler = useRef(onClick);
  useEffect(() => {
    handler.current = onClick;
  }, [onClick]);

  useEffect(() => {
    const chart = echarts.init(element.current!, undefined, { renderer: "canvas" });
    instance.current = chart;
    chart.on("click", (params) => {
      const data = (params as { data?: Record<string, unknown> }).data;
      if (data !== undefined) handler.current?.(data);
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element.current!);
    return () => {
      observer.disconnect();
      chart.dispose();
      instance.current = null;
    };
  }, []);

  useEffect(() => {
    instance.current?.setOption(option, { notMerge: true });
  }, [option]);

  return <div ref={element} role="img" aria-label={label} style={{ height, width: "100%" }} />;
}
