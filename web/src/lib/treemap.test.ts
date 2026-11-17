import { describe, expect, it } from "vitest";

import { squarify } from "./treemap";

const items = [6, 6, 4, 3, 2, 2, 1].map((value, i) => ({ id: i, value }));
const box = { h: 400, w: 600, x: 0, y: 0 };

describe("squarify", () => {
  const placed = squarify(items, box);

  it("gives each item an area proportional to its value", () => {
    const total = items.reduce((sum, item) => sum + item.value, 0);
    for (const tile of placed) {
      expect((tile.w * tile.h) / (box.w * box.h)).toBeCloseTo(tile.value / total, 9);
    }
  });
  it("fills the box exactly and stays inside it", () => {
    expect(placed.reduce((sum, tile) => sum + tile.w * tile.h, 0)).toBeCloseTo(box.w * box.h, 6);
    for (const tile of placed) {
      expect(tile.x).toBeGreaterThanOrEqual(-1e-9);
      expect(tile.y).toBeGreaterThanOrEqual(-1e-9);
      expect(tile.x + tile.w).toBeLessThanOrEqual(box.w + 1e-9);
      expect(tile.y + tile.h).toBeLessThanOrEqual(box.h + 1e-9);
    }
  });
  it("keeps tiles from overlapping", () => {
    for (const a of placed) {
      for (const b of placed) {
        if (a === b) continue;
        const overlapW = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        const overlapH = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        expect(overlapW <= 1e-6 || overlapH <= 1e-6).toBe(true);
      }
    }
  });
  it("drops items with no value", () => {
    expect(squarify([{ value: 0 }, { value: 5 }], box)).toHaveLength(1);
  });
});
