import { formatBasisPoints, formatPercent } from "./format";
import type { Instrument, Window } from "./types";

export interface Figure {
  /** The number the colour and sort follow: a return, or a yield change in points. */
  value: number;
  text: string;
}

/** A window's figure: a return for prices, a change in basis points for yields. */
export const figure = (instrument: Instrument, window: Window): Figure | null => {
  if (instrument.quoteType === "yield") {
    const change = instrument.metrics[`change_${window}`];
    return change == null ? null : { text: formatBasisPoints(change), value: change };
  }
  const change = instrument.metrics[`return_${window}`];
  return change == null ? null : { text: formatPercent(change), value: change };
};

/** The return of a window as a fraction, for ranking and colouring across kinds. */
export const returnOf = (instrument: Instrument, window: Window): number | null =>
  instrument.metrics[`return_${window}`] ?? null;
