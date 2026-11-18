import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";

import { Header } from "./components/Header";
import { SearchDialog } from "./components/SearchDialog";
import { Block, SlowNote } from "./components/Status";
import { loadBars } from "./lib/data";
import { judge } from "./lib/freshness";
import { useReady } from "./lib/ready";
import { MAX_COMPARE, useRoute, VIEW_LABELS } from "./lib/route";
import { useData, useNow } from "./lib/useData";
import { Markets } from "./views/Markets";

const Ticker = lazy(() => import("./views/Ticker"));
const Compare = lazy(() => import("./views/Compare"));
const Runs = lazy(() => import("./views/Runs"));
const Signals = lazy(() => import("./views/Signals"));

function Holding() {
  useReady(false);
  return (
    <div className="space-y-3" aria-busy="true">
      <Block height={88} />
      <Block height={360} />
    </div>
  );
}

export default function App() {
  const [route, update] = useRoute();
  const data = useData();
  const now = useNow();
  const [searching, setSearching] = useState(false);

  useLayoutEffect(() => {
    document.title = route.view === "markets" ? "Market data" : `${VIEW_LABELS[route.view]} · Market data`;
    document.documentElement.dataset.ready = "0";
    document.documentElement.dataset.view = route.view;
  }, [route.view]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      const target = event.target as HTMLElement | null;
      const typing = target !== null && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if ((event.key === "k" && (event.metaKey || event.ctrlKey)) || (event.key === "/" && !typing)) {
        event.preventDefault();
        setSearching(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const overview = data.overview.status === "ready" ? data.overview.value : null;
  const searchable = useMemo(() => [...(overview ?? [])].sort((a, b) => a.ticker.localeCompare(b.ticker)), [overview]);
  const freshness = data.runs.status === "ready" ? judge(data.runs.value, now) : null;
  const lastDay = data.latest?.day ?? null;

  const pick = useCallback(
    (ticker: string) => {
      setSearching(false);
      if (route.view === "compare") {
        if (!route.compare.includes(ticker) && route.compare.length < MAX_COMPARE) update({ compare: [...route.compare, ticker] });
      } else {
        update({ ticker, view: "ticker" });
      }
    },
    [route.view, route.compare, update],
  );

  return (
    <>
      <Header view={route.view} onView={(view) => update({ view })} onSearch={() => setSearching(true)} freshness={freshness} ageUnknown={data.runs.status === "error"} lastDay={lastDay} now={now} />
      <main className="mx-auto max-w-[1280px] px-3 py-3 sm:px-4 sm:py-4">
        {data.overview.status === "loading" && <SlowNote />}
        <Suspense fallback={<Holding />}>
          {route.view === "markets" && <Markets data={data} route={route} update={update} />}
          {route.view === "ticker" && <Ticker data={data} route={route} update={update} onSearch={() => setSearching(true)} />}
          {route.view === "compare" && <Compare data={data} route={route} update={update} onSearch={() => setSearching(true)} />}
          {route.view === "signals" && <Signals data={data} route={route} update={update} />}
          {route.view === "runs" &&<Runs data={data} now={now} />}
        </Suspense>
      </main>
      <SearchDialog
        open={searching}
        instruments={searchable}
        onClose={() => setSearching(false)}
        onPick={(item) => pick(item.ticker)}
        onHighlight={(item) => void loadBars(item.slug, data.version).catch(() => undefined)}
        hint={route.view === "compare" ? "Enter adds to the comparison" : "Enter opens the instrument"}
      />
    </>
  );
}
