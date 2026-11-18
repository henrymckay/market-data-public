import { CircleAlert, CircleCheck, TriangleAlert } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { cn } from "../lib/cn";

export type Tone = "good" | "warning" | "critical" | "neutral";

const TONES: Record<Tone, { icon: typeof CircleCheck; text: string; dot: string }> = {
  critical: { dot: "text-critical-text", icon: CircleAlert, text: "text-critical-text" },
  good: { dot: "text-good-text", icon: CircleCheck, text: "text-foreground" },
  neutral: { dot: "text-muted-foreground", icon: CircleCheck, text: "text-text-2" },
  warning: { dot: "text-warning-text", icon: TriangleAlert, text: "text-foreground" },
};

/** A status as icon plus words, never colour alone. */
export function StatusChip({ tone, children, title, className }: { tone: Tone; children: ReactNode; title?: string; className?: string }) {
  const { icon: Icon, text, dot } = TONES[tone];
  return (
    <span title={title} className={cn("inline-flex items-center gap-1.5 text-sm font-medium", text, className)}>
      <Icon size={16} aria-hidden="true" className={dot} />
      {children}
    </span>
  );
}

/** An error inside the card that failed; the rest of the page keeps working. */
export function ErrorNote({ children, onRetry }: { children: ReactNode; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-md border border-critical/40 bg-muted p-3 text-sm">
      <CircleAlert size={16} aria-hidden="true" className="mt-0.5 shrink-0 text-critical-text" />
      <div className="min-w-0">
        <div>{children}</div>
        {onRetry !== undefined && (
          <button type="button" onClick={onRetry} className="mt-1 font-medium text-up-text underline underline-offset-2">
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">{children}</div>;
}

export function Block({ height, className }: { height: number; className?: string }) {
  return <div className={cn("skeleton w-full", className)} style={{ height }} aria-hidden="true" />;
}

/** Says a load is still going once it has run `afterMs`; mount it only while loading. */
export function SlowNote({ afterMs = 3_000 }: { afterMs?: number }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), afterMs);
    return () => clearTimeout(timer);
  }, [afterMs]);
  if (!slow) return null;
  return (
    <p role="status" className="mb-3 text-sm text-muted-foreground">
      Still loading. The first request after a new run can take a few seconds.
    </p>
  );
}
