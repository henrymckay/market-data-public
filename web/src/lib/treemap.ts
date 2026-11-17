export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type Placed<T> = T & Rect;

/** Lay items out as a squarified treemap: areas proportional to value, aspect ratios near 1. */
export const squarify = <T extends { value: number }>(items: readonly T[], box: Rect): Placed<T>[] => {
  const positive = items.filter((item) => item.value > 0).sort((a, b) => b.value - a.value);
  const total = positive.reduce((sum, item) => sum + item.value, 0);
  const out: Placed<T>[] = [];
  if (total === 0 || box.w <= 0 || box.h <= 0) return out;
  const scale = (box.w * box.h) / total;
  let rest = { ...box };
  let row: T[] = [];

  const worst = (candidates: readonly T[], side: number): number => {
    const areas = candidates.map((item) => item.value * scale);
    const sum = areas.reduce((a, b) => a + b, 0);
    const max = Math.max(...areas);
    const min = Math.min(...areas);
    return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));
  };

  const place = (): void => {
    const sum = row.reduce((a, item) => a + item.value * scale, 0);
    const horizontal = rest.w >= rest.h;
    const side = horizontal ? rest.h : rest.w;
    const thickness = sum / side;
    let offset = 0;
    for (const item of row) {
      const length = (item.value * scale) / thickness;
      out.push(
        horizontal
          ? { ...item, h: length, w: thickness, x: rest.x, y: rest.y + offset }
          : { ...item, h: thickness, w: length, x: rest.x + offset, y: rest.y },
      );
      offset += length;
    }
    rest = horizontal
      ? { h: rest.h, w: rest.w - thickness, x: rest.x + thickness, y: rest.y }
      : { h: rest.h - thickness, w: rest.w, x: rest.x, y: rest.y + thickness };
    row = [];
  };

  for (const item of positive) {
    const side = Math.min(rest.w, rest.h);
    if (row.length === 0 || worst([...row, item], side) <= worst(row, side)) row.push(item);
    else {
      place();
      row.push(item);
    }
  }
  if (row.length > 0) place();
  return out;
};
