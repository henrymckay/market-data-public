const parse = (hex: string): [number, number, number] => {
  const value = hex.replace("#", "");
  const full = value.length === 3 ? [...value].map((c) => c + c).join("") : value.slice(0, 6);
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16)) as [number, number, number];
};

const toHex = (rgb: readonly number[]): string =>
  `#${rgb.map((c) => Math.round(c).toString(16).padStart(2, "0")).join("")}`;

export const mix = (from: string, to: string, amount: number): string => {
  const a = parse(from);
  const b = parse(to);
  return toHex(a.map((c, i) => c + (b[i]! - c) * amount));
};

const luminance = (hex: string): number => {
  const channels = parse(hex).map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0]! + 0.7152 * channels[1]! + 0.0722 * channels[2]!;
};

export const contrast = (a: string, b: string): number => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
};

/** Whichever of the two inks reads better on the fill. */
export const inkOn = (fill: string, light: string, dark: string): string =>
  contrast(fill, light) >= contrast(fill, dark) ? light : dark;

/** The diverging scale: blue for a rise, red for a fall, through `sunken`, saturating at `bound`. */
export const diverging = (
  value: number,
  bound: number,
  roles: { up: string; down: string; sunken: string },
): string => {
  const amount = Math.min(1, Math.abs(value) / bound);
  return mix(roles.sunken, value >= 0 ? roles.up : roles.down, amount);
};
