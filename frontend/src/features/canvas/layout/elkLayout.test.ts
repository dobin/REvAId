/**
 * Regression tests for the "fanned-out card lands on top of an existing
 * card" bug. Two distinct defects produced that symptom:
 *
 * 1. `elk.spacing.nodeNodeBetweenLayers` is not a real ELK option (the
 *    layered algorithm reads `elk.layered.spacing.nodeNodeBetweenLayers`), so
 *    the configured 80px inter-layer gap was silently ignored in favour of
 *    elkjs's own 20px default.
 * 2. Pinned nodes (D15) are deliberately withheld from the ELK graph so ELK
 *    can never move them — but that also means ELK lays the remaining block
 *    out from its own origin, straight on top of the pinned card, unless the
 *    pinned rectangles are re-applied afterwards as obstacles.
 */
import { describe, expect, it } from "vitest";
import {
  computeElkLayout,
  offsetPastObstacles,
  type LayoutObstacle,
  type LayoutPositions,
} from "./elkLayout";

const CARD_WIDTH = 380;

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

function overlaps(a: Rect, b: Rect): boolean {
  const overlapsX = a.x < b.x + b.width && a.x + a.width > b.x;
  const overlapsY = a.y < b.y + b.height && a.y + a.height > b.y;
  return overlapsX && overlapsY;
}

/** Reads a position out of a layout result, failing the test if it's absent
 * (rather than reaching for a non-null assertion the lint config forbids). */
function positionOf(positions: LayoutPositions, id: string): { x: number; y: number } {
  const pos = positions[id];
  if (!pos) throw new Error(`no position computed for node ${id}`);
  return pos;
}

describe("computeElkLayout", () => {
  it("separates two chained cards by their real widths, not a default gap", async () => {
    // Layout direction is RIGHT (a callee sits to the right of its caller,
    // not below it), so successive layers are separated along x.
    const positions = await computeElkLayout(
      [
        { id: "1", width: CARD_WIDTH, height: 546 },
        { id: "2", width: CARD_WIDTH, height: 599 },
      ],
      [{ id: "1->2", source: "1", target: "2" }],
    );

    const first = positionOf(positions, "1");
    const second = positionOf(positions, "2");

    // The child must start strictly right of the parent's full measured
    // width, and by the configured inter-layer spacing rather than elkjs's
    // own 20px default — a regression to the mis-spelled option key makes
    // this 20.
    expect(second.x - (first.x + CARD_WIDTH)).toBeGreaterThanOrEqual(80);
  });

  it("lays a caller (fanin) left and a callee (fanout) right of the centre", async () => {
    // The oriented edges deriveCanvasEdges produces for a centre card (id 1)
    // with a fanned-out caller (id 2, fanin -> edge 2->1) and a fanned-out
    // callee (id 3, fanout -> edge 1->3). ELK direction RIGHT lays each
    // source left of its target, so: caller.x < centre.x < callee.x.
    const positions = await computeElkLayout(
      [
        { id: "1", width: CARD_WIDTH, height: 240 },
        { id: "2", width: CARD_WIDTH, height: 240 },
        { id: "3", width: CARD_WIDTH, height: 240 },
      ],
      [
        { id: "1->2", source: "2", target: "1" }, // fanin caller
        { id: "1->3", source: "1", target: "3" }, // fanout callee
      ],
    );

    const caller = positionOf(positions, "2");
    const centre = positionOf(positions, "1");
    const callee = positionOf(positions, "3");

    expect(caller.x).toBeLessThan(centre.x);
    expect(centre.x).toBeLessThan(callee.x);
  });

  it("never overlaps any pair of cards in a deep chain of mixed heights", async () => {
    const heights = [546, 1197, 240, 880, 96];
    const nodes = heights.map((height, i) => ({
      id: String(i),
      width: CARD_WIDTH,
      height,
    }));
    const edges = heights.slice(1).map((_, i) => ({
      id: `${String(i)}->${String(i + 1)}`,
      source: String(i),
      target: String(i + 1),
    }));

    const positions = await computeElkLayout(nodes, edges);

    const rects: Rect[] = nodes.map((n) => ({
      ...positionOf(positions, n.id),
      width: n.width,
      height: n.height,
    }));

    for (let i = 0; i < rects.length; i += 1) {
      for (let j = i + 1; j < rects.length; j += 1) {
        const a = rects[i];
        const b = rects[j];
        if (!a || !b) throw new Error("missing rect");
        expect(overlaps(a, b), `nodes ${String(i)} and ${String(j)} overlap`).toBe(false);
      }
    }
  });

  it("places the laid-out block clear of a pinned card's rectangle", async () => {
    // Mirrors the live repro: `main` was dragged (pinned) to (16,24); a
    // fan-out then produced a node ELK placed at its origin. With layout
    // direction RIGHT, the block must clear the obstacle horizontally.
    const positions = await computeElkLayout(
      [{ id: "2", width: CARD_WIDTH, height: 599 }],
      [],
      [{ x: 16, y: 24, width: CARD_WIDTH, height: 546 }],
    );

    expect(positionOf(positions, "2").x).toBeGreaterThanOrEqual(16 + CARD_WIDTH);
  });
});

describe("offsetPastObstacles", () => {
  const sizes = new Map([
    ["a", { width: CARD_WIDTH, height: 200 }],
    ["b", { width: CARD_WIDTH, height: 300 }],
  ]);
  const block: LayoutPositions = { a: { x: 0, y: 0 }, b: { x: 0, y: 280 } };

  it("is a no-op when there are no obstacles", () => {
    expect(offsetPastObstacles(block, sizes, [])).toBe(block);
  });

  it("is a no-op when nothing actually collides", () => {
    // Obstacle sits far below — no vertical overlap at all.
    const result = offsetPastObstacles(block, sizes, [
      { x: 0, y: 5000, width: CARD_WIDTH, height: 400 },
    ]);
    expect(result).toEqual(block);
  });

  it("shifts the whole block rigidly, preserving relative layering", () => {
    const result = offsetPastObstacles(block, sizes, [
      { x: 0, y: 0, width: 500, height: 400 },
    ]);

    // Both nodes moved by the same amount: the layering ELK computed is the
    // whole point of running it, so it must survive the offset pass.
    const deltaA = positionOf(result, "a").x - positionOf(block, "a").x;
    const deltaB = positionOf(result, "b").x - positionOf(block, "b").x;
    expect(deltaA).toBe(deltaB);
    expect(deltaA).toBeGreaterThan(0);
    // Clears the obstacle's right edge, and never touches y.
    expect(positionOf(result, "a").x).toBeGreaterThanOrEqual(500);
    expect(positionOf(result, "a").y).toBe(0);
  });

  it("clears a second obstacle it slid into while clearing the first", () => {
    const obstacles: LayoutObstacle[] = [
      { x: 0, y: 0, width: 300, height: 400 },
      // Sits just past where clearing the first obstacle lands the block.
      { x: 380, y: 0, width: 300, height: 400 },
    ];
    const result = offsetPastObstacles(block, sizes, obstacles);

    for (const [id, pos] of Object.entries(result)) {
      const size = sizes.get(id);
      if (!size) throw new Error(`no size for ${id}`);
      for (const obstacle of obstacles) {
        expect(
          overlaps({ ...pos, ...size }, obstacle),
          `${id} still overlaps an obstacle`,
        ).toBe(false);
      }
    }
  });

  it("ignores nodes it has no size for rather than throwing", () => {
    const positions: LayoutPositions = { unknown: { x: 0, y: 0 } };
    expect(
      offsetPastObstacles(positions, sizes, [
        { x: 0, y: 0, width: 400, height: 400 },
      ]),
    ).toEqual(positions);
  });
});
