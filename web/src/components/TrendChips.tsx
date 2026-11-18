import { ArrowDown, ArrowDownRight, ArrowUp, ArrowUpRight, Minus } from "lucide-react";

import { cn } from "../lib/cn";
import { TIMEFRAME_WORDS, TIMEFRAMES, type Timeframe } from "../lib/signals";
import type { Instrument, TrendState } from "../lib/types";

const STATE_WORDS: Record<TrendState, string> = {
  down: "down",
  none: "none yet",
  turning_down: "turning down",
  turning_up: "turning up",
  up: "up",
};

const ICON = { down: ArrowDown, none: Minus, turning_down: ArrowDownRight, turning_up: ArrowUpRight, up: ArrowUp } as const;
const TONE = { down: "text-down-text", none: "text-muted-foreground", turning_down: "text-down-text", turning_up: "text-up-text", up: "text-up-text" } as const;

/** Three chips, D W M: an arrow for each timeframe's trend, its state in words for a screen reader. */
export function TrendChips({ item }: { item: Instrument }) {
  return (
    <span className="relative inline-flex items-center gap-1.5" role="group" aria-label={`Trend of ${item.ticker}`}>
      {TIMEFRAMES.map((frame: Timeframe) => {
        const state = item.trend[frame];
        const Icon = state === null ? Minus : ICON[state];
        const words = state === null ? "no structure yet" : STATE_WORDS[state];
        return (
          <span key={frame} title={`${TIMEFRAME_WORDS[frame]}: ${words}`} className={cn("inline-flex items-center gap-px rounded border px-1 text-xs font-medium", state === null ? "text-muted-foreground" : TONE[state])}>
            <span aria-hidden="true">{frame.toUpperCase()}</span>
            <Icon size={12} aria-hidden="true" />
            <span className="sr-only">{`${TIMEFRAME_WORDS[frame]} trend ${words}`}</span>
          </span>
        );
      })}
    </span>
  );
}
