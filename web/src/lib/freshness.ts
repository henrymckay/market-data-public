import type { Run } from "./types";

export type Level = "fresh" | "stale" | "partial" | "failed" | "none";

export interface Freshness {
  level: Level;
  /** The age of the last stored `yahoo` run in milliseconds, or null with none. */
  ageMs: number | null;
  /** When that run ended, as an ISO moment. */
  ended: string | null;
  label: string;
}

const STALE_AFTER_MS = 2 * 86_400_000;

/**
 * Judge the data's freshness as `status` does: failed when the last run failed,
 * partial when it was partial, stale when the last stored yahoo run is over two
 * days old.
 */
export const judge = (runs: readonly Run[], now: number): Freshness => {
  if (runs.length === 0) return { ageMs: null, ended: null, label: "No runs yet", level: "none" };
  const byEnd = [...runs].sort((a, b) => Date.parse(b.ended) - Date.parse(a.ended));
  const last = byEnd[0]!;
  const stored = byEnd.find((run) => run.source === "yahoo" && run.outcome === "stored");
  const ageMs = stored === undefined ? null : now - Date.parse(stored.ended);
  const ended = stored?.ended ?? null;
  if (last.outcome === "failed") return { ageMs, ended, label: "Last run failed", level: "failed" };
  if (ageMs === null || ageMs > STALE_AFTER_MS) return { ageMs, ended, label: "Prices are stale", level: "stale" };
  if (last.outcome === "partial") return { ageMs, ended, label: "Last run partial", level: "partial" };
  return { ageMs, ended, label: "Up to date", level: "fresh" };
};
