import { useCallback, useEffect, useRef, useState } from "react";

import { loadLatest, loadOverview, loadRuns } from "./data";
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
        known.current = value?.ended ?? null;
        setLatest(value);
      },
      () => undefined,
    );
    const timer = setInterval(() => {
      loadLatest().then(
        (value) => {
          setLatest(value);
          const ended = value?.ended ?? null;
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

/** The current time, refreshed on a slow clock so an age judged from it stays honest. */
export const useNow = (everyMs = 60_000): number => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(timer);
  }, [everyMs]);
  return now;
};
