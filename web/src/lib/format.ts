const MINUS = "−";

const integer = new Intl.NumberFormat("en-GB");
const compact = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1, notation: "compact" });
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fixed = new Map<number, Intl.NumberFormat>();
const withDigits = (digits: number): Intl.NumberFormat => {
  let format = fixed.get(digits);
  if (format === undefined) {
    format = new Intl.NumberFormat("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits });
    fixed.set(digits, format);
  }
  return format;
};

/** Replace the hyphen of a negative number with a true minus sign. */
export const minus = (text: string): string => text.replace("-", MINUS);

export const formatInteger = (n: number): string => minus(integer.format(n));

export const formatCompact = (n: number): string => minus(compact.format(n)).replace("k", "K");

export const formatFixed = (n: number, digits: number): string => minus(withDigits(digits).format(n));

/** Decimals for a quoted price: currencies to four places, small prices too, the rest two. */
export const priceDigits = (value: number, assetClass: string): number => {
  if (assetClass === "fx") return value >= 20 ? 3 : 4;
  return Math.abs(value) < 1 ? 4 : 2;
};

export const formatPrice = (value: number, assetClass: string): string =>
  formatFixed(value, priceDigits(value, assetClass));

/** A tile's value: full to two places, compact from 50,000. */
export const formatTileValue = (value: number, assetClass: string): string =>
  Math.abs(value) >= 50_000 ? formatCompact(value) : formatPrice(value, assetClass);

/** A fraction as a signed percentage to two places: 0.0084 gives +0.84%. */
export const formatPercent = (fraction: number): string => {
  const text = formatFixed(fraction * 100, 2);
  if (text === "0.00" || text === `${MINUS}0.00`) return "0.00%";
  return `${fraction < 0 ? "" : "+"}${text}%`;
};

/** A fraction as an unsigned percentage to a chosen number of places. */
export const formatShare = (fraction: number, digits = 1): string => `${formatFixed(fraction * 100, digits)}%`;

/** A yield change in percentage points as signed basis points: 0.033 gives +3 bp. */
export const formatBasisPoints = (points: number): string => {
  const bp = Math.sign(points) * Math.round(Math.abs(points) * 100);
  if (bp === 0) return "0 bp";
  return `${bp > 0 ? "+" : MINUS}${integer.format(Math.abs(bp))} bp`;
};

export const formatYield = (value: number): string => `${formatFixed(value, 2)}%`;

/** An ISO day as `12 Nov 2026`, with a fixed month abbreviation whatever the runtime's locale data. */
export const formatDay = (iso: string): string =>
  `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}`;

/** A UTC moment as `17 Nov 2026, 08:42 UTC`. */
export const formatMoment = (iso: string): string => {
  const date = new Date(iso);
  const hh = String(date.getUTCHours()).padStart(2, "0");
  const mm = String(date.getUTCMinutes()).padStart(2, "0");
  return `${formatDay(date.toISOString().slice(0, 10))}, ${hh}:${mm} UTC`;
};

/** An age in milliseconds as `7 h ago`. */
export const formatAge = (milliseconds: number): string => {
  const minutes = Math.max(0, Math.round(milliseconds / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
};

/** A short duration as `1 min 59 s` between two ISO moments. */
export const formatDuration = (startIso: string, endIso: string): string => {
  const seconds = Math.max(0, Math.round((Date.parse(endIso) - Date.parse(startIso)) / 1000));
  if (seconds < 60) return `${seconds} s`;
  return `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
};
