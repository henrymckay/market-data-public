import { useCallback, useEffect, useRef, useState } from "react";

import { loadLatest, loadOverview, loadRuns, loadSignals, loadStats } from "./data";
import type { Signal, Stat } from "./signals";
import type { Instrument, Latest, Run } from "./types";

export type Loaded<T> = { status: "loading" } | { status: "error" } | { status: "ready"; value: T };

export interface Data {
  overview: Loaded<Instrument[]>;
  runs: Loaded<Run[]>;
  latest: Latest | null;
  /** The run the data belongs to, or undefined for the first load; keys per-run caches. */
  version: string | undefined;
  reload: () => void;
}

const POLL_MS = 300_000;

/** What the API's cache is keyed on: the metrics or signals run's end, else the yahoo run's. */
const stampOf = (latest: Latest | null): string | null => latest?.version ?? latest?.ended ?? null;

/** The API's data, refetched when the latest run's `ended` changes. */
export const useData = (): Data => {
  const [overview, setOverview] = useState<Loaded<Instrument[]>>({ status: "loading" });
  const [runs, setRuns] = useState<Loaded<Run[]>>({ status: "loading" });
  const [latest, setLatest] = useState<Latest | null>(null);
  const [version, setVersion] = useState<string | undefined>(undefined);
  const known = useRef<string | null | undefined>(undefined);

  const load = useCallback((tag?: string) => {
    loadOverview(tag).then(
      (value) => setOverview({ status: "ready", value }),
      () => setOverview({ status: "error" }),
    );
    loadRuns(tag).then(
      (value) => setRuns({ status: "ready", value }),
      () => setRuns({ status: "error" }),
    );
  }, []);

  const reload = useCallback(() => {
    setOverview({ status: "loading" });
    setRuns({ status: "loading" });
    load(known.current ?? undefined);
  }, [load]);

  useEffect(() => {
    load();
    loadLatest().then(
      (value) => {
        known.current = stampOf(value);
        setLatest(value);
      },
      () => undefined,
    );
    const timer = setInterval(() => {
      loadLatest().then(
        (value) => {
          setLatest(value);
          const ended = stampOf(value);
          if (known.current !== undefined && ended !== known.current && ended !== null) {
            setVersion(ended);
            load(ended);
          }
          known.current = ended;
        },
        () => undefined,
      );
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [load]);

  return { latest, overview, reload, runs, version };
};

export type Signalled = { status: "loading" } | { status: "error" } | { status: "ready"; signals: Signal[]; stats: Stat[] };

/** The signals and base rates for a data version; both are fetched once and shared by every screen. */
export const useSignals = (version: string | undefined, attempt = 0, wanted = true): Signalled => {
  const [loaded, setLoaded] = useState<{ key: string; value: Signalled } | null>(null);
  const key = `${version ?? ""}|${attempt}`;
  useEffect(() => {
    if (!wanted) return undefined;
    let current = true;
    Promise.all([loadSignals(version), loadStats(version)]).then(
      ([signals, stats]) => current && setLoaded({ key, value: { signals, stats, status: "ready" } }),
      () => current && setLoaded({ key, value: { status: "error" } }),
    );
    return () => {
      current = false;
    };
  }, [version, key, wanted]);
  return loaded !== null && loaded.key === key ? loaded.value : { status: "loading" };
};

/** The current time, refreshed on a slow clock so an age judged from it stays honest. */
export const useNow = (everyMs = 60_000): number => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(timer);
  }, [everyMs]);
  return now;
};
