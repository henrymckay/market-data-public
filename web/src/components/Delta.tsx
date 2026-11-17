import { cn } from "../lib/cn";

interface DeltaProps {
  value: number | null;
  text: string | null;
  className?: string;
}

/** A signed change: blue up, red down, muted when flat or absent; the sign always prints. */
export function Delta({ value, text, className }: DeltaProps) {
  if (value === null || text === null) return <span className={cn("text-muted-foreground", className)}>–</span>;
  const tone = Math.abs(value) < 1e-12 ? "text-muted-foreground" : value > 0 ? "text-up-text" : "text-down-text";
  return <span className={cn("num", tone, className)}>{text}</span>;
}
