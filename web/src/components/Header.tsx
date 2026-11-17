import { CircleAlert, CircleCheck, Moon, Search, Sun, TriangleAlert } from "lucide-react";

import { cn } from "../lib/cn";
import { formatAge, formatDay, formatMoment } from "../lib/format";
import type { Freshness } from "../lib/freshness";
import { VIEW_LABELS, VIEWS, type View } from "../lib/route";
import { useTheme } from "../lib/theme";

interface HeaderProps {
  view: View;
  onView: (view: View) => void;
  onSearch: () => void;
  freshness: Freshness | null;
  lastDay: string | null;
  now: number;
}

const ICONS = { critical: CircleAlert, good: CircleCheck, warning: TriangleAlert } as const;

function AgeChip({ freshness, lastDay }: { freshness: Freshness | null; lastDay: string | null; now: number }) {
  if (freshness === null) return <div className="skeleton h-5 w-40" aria-hidden="true" />;
  const tone = freshness.level === "failed" ? "critical" : freshness.level === "fresh" ? "good" : "warning";
  const Icon = ICONS[tone];
  const color = tone === "critical" ? "text-critical-text" : tone === "warning" ? "text-warning-text" : "text-good-text";
  const age = freshness.ageMs === null ? null : formatAge(freshness.ageMs);
  const title = freshness.ended === null ? freshness.label : `Last stored run ended ${formatMoment(freshness.ended)}. ${freshness.label}.`;
  return (
    <div role="status" title={title} className="flex min-w-0 items-center gap-1.5 text-sm text-text-2">
      <Icon size={16} aria-hidden="true" className={cn("shrink-0", color)} />
      <span className="truncate">
        {freshness.level !== "fresh" && <span className="mr-1.5 font-medium text-foreground">{freshness.label}.</span>}
        <span className="hidden md:inline">{lastDay === null ? "" : `Prices to ${formatDay(lastDay)} · `}</span>
        {age === null ? "no stored run" : <>run {age}</>}
      </span>
    </div>
  );
}

export function Header({ view, onView, onSearch, freshness, lastDay, now }: HeaderProps) {
  const { scheme, toggle } = useTheme();
  const next = scheme === "dark" ? "light" : "dark";
  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto grid max-w-[1280px] grid-cols-[auto_minmax(0,1fr)] gap-x-3 px-3 sm:px-4 md:grid-cols-[auto_auto_minmax(0,1fr)] md:gap-x-5">
        <a
          href="./"
          className="flex h-14 items-center gap-2 text-lg font-semibold text-foreground no-underline"
          onClick={(e) => {
            e.preventDefault();
            onView("markets");
          }}
        >
          <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" width={24} height={24} className="rounded-md" />
          Market data
        </a>
        <div className="col-start-2 row-start-1 flex min-w-0 items-center justify-end gap-2 sm:gap-3 md:col-start-3">
          <button
            type="button"
            onClick={onSearch}
            aria-label="Search instruments"
            className="flex h-8 shrink-0 items-center gap-2 rounded-md border border-input bg-card px-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground sm:w-48"
          >
            <Search size={16} aria-hidden="true" />
            <span className="hidden sm:inline">Search</span>
            <kbd className="ml-auto hidden rounded bg-muted px-1.5 text-xs font-medium sm:inline">/</kbd>
          </button>
          <AgeChip freshness={freshness} lastDay={lastDay} now={now} />
          <button
            type="button"
            onClick={toggle}
            aria-label={`Switch to the ${next} scheme`}
            className="grid size-8 shrink-0 place-items-center rounded-md text-text-2 transition-colors hover:bg-muted hover:text-foreground"
          >
            {scheme === "dark" ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
          </button>
        </div>
        <nav
          aria-label="Screens"
          className="scroll-thin col-span-full row-start-2 -mx-1 flex items-center gap-1 overflow-x-auto pb-2 md:col-span-1 md:col-start-2 md:row-start-1 md:mx-0 md:pb-0"
        >
          {VIEWS.map((v) => (
            <a
              key={v}
              href={`?view=${v}`}
              data-view={v}
              aria-current={v === view ? "page" : undefined}
              onClick={(e) => {
                e.preventDefault();
                onView(v);
              }}
              className={cn(
                "rounded-md px-3 py-1.5 text-base font-medium no-underline transition-colors",
                v === view ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {VIEW_LABELS[v]}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
