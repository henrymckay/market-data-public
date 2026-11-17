import type { ReactNode } from "react";

import { cn } from "../lib/cn";

interface TileProps {
  label: string;
  value: ReactNode;
  context?: ReactNode;
  delta?: ReactNode;
  spark?: ReactNode;
  valueTitle?: string;
  onClick?: () => void;
  className?: string;
}

/** The answer: a muted label, the value, then a muted line of context. */
export function Tile({ label, value, valueTitle, context, delta, spark, onClick, className }: TileProps) {
  const body = (
    <>
      <div className="truncate text-sm text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-2xl font-semibold leading-8 num" title={valueTitle}>{value}</div>
      <div className="mt-1 flex items-end justify-between gap-2 text-sm">
        {delta !== undefined && <div className="font-medium">{delta}</div>}
        {spark}
      </div>
      {context !== undefined && <div className="mt-0.5 text-sm text-muted-foreground">{context}</div>}
    </>
  );
  const shell = cn("min-w-0 rounded-lg border bg-card p-3 text-left sm:p-4", className);
  if (onClick === undefined) return <div className={shell}>{body}</div>;
  return (
    <button type="button" onClick={onClick} className={cn(shell, "transition-colors hover:bg-muted")}>
      {body}
    </button>
  );
}

export function TileSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-3 sm:p-4" aria-hidden="true">
      <div className="skeleton h-4 w-24" />
      <div className="skeleton mt-2 h-8 w-32" />
      <div className="skeleton mt-2 h-5 w-20" />
    </div>
  );
}
