import { ArrowDown, ArrowUp, Check, X } from "lucide-react";

import { cn } from "../lib/cn";
import { EVENT_WORDS, type Signal } from "../lib/signals";

/** A grade as a letter in a chip: the letter carries it, the tint only helps. */
export function GradeChip({ grade }: { grade: Signal["grade"] }) {
  return (
    <span
      title={`Graded ${grade}`}
      className={cn(
        "inline-grid h-5 min-w-5 place-items-center rounded border px-1 text-xs font-semibold",
        grade === "A" ? "border-primary bg-primary/10 text-up-text" : grade === "B" ? "text-text-2" : "text-muted-foreground",
      )}
    >
      {grade}
    </span>
  );
}

/** The event in the owner's words with an arrow the way it points. */
export function EventLabel({ event, direction }: Pick<Signal, "event" | "direction">) {
  const Icon = direction === "up" ? ArrowUp : ArrowDown;
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      <Icon size={14} aria-hidden="true" className={direction === "up" ? "text-up-text" : "text-down-text"} />
      {EVENT_WORDS[event]}
    </span>
  );
}

/** Whether the stop has held so far, as an icon and a word. */
export function HeldMark({ held }: { held: boolean | null }) {
  if (held === null) return <span className="text-muted-foreground">–</span>;
  const Icon = held ? Check : X;
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      <Icon size={14} aria-hidden="true" className={held ? "text-good-text" : "text-critical-text"} />
      {held ? "Held" : "Broken"}
    </span>
  );
}
