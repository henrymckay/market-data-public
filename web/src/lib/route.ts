import { useCallback, useSyncExternalStore } from "react";

import { RANGES, type Range } from "./stats";
import { WINDOWS, type Window } from "./types";

export const VIEWS = ["markets", "ticker", "compare", "runs"] as const;
export type View = (typeof VIEWS)[number];

export const VIEW_LABELS: Record<View, string> = {
  compare: "Compare",
  markets: "Markets",
  runs: "Runs",
  ticker: "Ticker",
};

export interface Route {
  view: View;
  period: Window;
  ticker: string;
  range: Range;
  ma50: boolean;
  ma200: boolean;
  log: boolean;
  compare: string[];
  assetClass: string;
  sort: string;
  dir: "asc" | "desc";
}

export const DEFAULT_COMPARE = ["^GSPC", "^NDX", "GC=F", "BTC-USD"];
export const MAX_COMPARE = 6;

export const parseRoute = (search: string): Route => {
  const q = new URLSearchParams(search);
  const view = q.get("view");
  const period = q.get("period");
  const range = q.get("range");
  const compare = q.get("c");
  return {
    assetClass: q.get("cls") ?? "all",
    compare: compare === null ? DEFAULT_COMPARE : compare.split(",").filter(Boolean).slice(0, MAX_COMPARE),
    dir: q.get("dir") === "asc" ? "asc" : "desc",
    log: q.get("log") === "1",
    ma200: q.get("ma200") === "1",
    ma50: q.get("ma50") === "1",
    period: (WINDOWS as readonly string[]).includes(period ?? "") ? (period as Window) : "1d",
    range: (RANGES as readonly string[]).includes(range ?? "") ? (range as Range) : "1Y",
    sort: q.get("sort") ?? "",
    ticker: q.get("t") ?? "^GSPC",
    view: (VIEWS as readonly string[]).includes(view ?? "") ? (view as View) : "markets",
  };
};

const DEFAULTS = parseRoute("");

/** Only what differs from the defaults goes in the query string. */
export const serializeRoute = (route: Route): string => {
  const q = new URLSearchParams();
  const set = (key: string, value: string, fallback: string): void => {
    if (value !== fallback) q.set(key, value);
  };
  set("view", route.view, DEFAULTS.view);
  if (route.view === "markets") {
    set("period", route.period, DEFAULTS.period);
    set("cls", route.assetClass, DEFAULTS.assetClass);
    set("sort", route.sort, DEFAULTS.sort);
    if (route.sort !== "") set("dir", route.dir, DEFAULTS.dir);
  }
  if (route.view === "ticker") {
    set("t", route.ticker, DEFAULTS.ticker);
    set("range", route.range, DEFAULTS.range);
    if (route.ma50) q.set("ma50", "1");
    if (route.ma200) q.set("ma200", "1");
    if (route.log) q.set("log", "1");
  }
  if (route.view === "compare") {
    set("range", route.range, DEFAULTS.range);
    if (route.compare.join(",") !== DEFAULT_COMPARE.join(",")) q.set("c", route.compare.join(","));
  }
  const text = q.toString().replace(/%5E/g, "^").replace(/%2C/g, ",").replace(/%3D/g, "=");
  return text === "" ? "" : `?${text}`;
};

const listeners = new Set<() => void>();
const subscribe = (listener: () => void): (() => void) => {
  listeners.add(listener);
  window.addEventListener("popstate", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("popstate", listener);
  };
};
const snapshot = (): string => window.location.search;

export const useRoute = (): [Route, (patch: Partial<Route>) => void] => {
  const search = useSyncExternalStore(subscribe, snapshot);
  const route = parseRoute(search);
  const update = useCallback((patch: Partial<Route>) => {
    const next = { ...parseRoute(window.location.search), ...patch };
    const url = `${window.location.pathname}${serializeRoute(next)}`;
    window.history.pushState(null, "", url);
    for (const listener of listeners) listener();
  }, []);
  return [route, update];
};
