/**
 * ELK layout computation (D11, TAD §2.5). Runs `elkjs`'s `layered` algorithm.
 *
 * NOT run in a dedicated Web Worker, despite the TAD's §2.5 sketch: `elkjs`'s
 * bundled build (`elk.bundled.js`) already manages its own internal worker
 * when constructed on the main thread (it detects a main-thread context via
 * `typeof document !== "undefined"` and wires up a fake in-process worker
 * accordingly). Wrapping that same bundle inside a *second*, real
 * `dedicated Worker` breaks this self-detection (`document` is undefined
 * inside a Worker) and elkjs throws `_Worker is not a constructor` — the
 * layout silently never runs, and every node falls back to its default
 * position (observed as new fan-out cards landing on top of their parent).
 * `elk.layout()` is itself async (a Promise) and, at the node counts this
 * app targets (`NODE_COUNT_SOFT_WARNING = 150`, typically ~10), does not
 * block the main thread long enough to matter.
 */
import ELK from "elkjs/lib/elk.bundled.js";

export interface LayoutInputNode {
  id: string;
  width: number;
  height: number;
}

export interface LayoutInputEdge {
  id: string;
  source: string;
  target: string;
}

/** A node ELK must not move (D15) but must not be covered by, either —
 * its rectangle is an obstacle the laid-out block gets pushed clear of. */
export interface LayoutObstacle {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type LayoutPositions = Record<string, { x: number; y: number }>;

/** ELK's `elk.layered.spacing.nodeNodeBetweenLayers` — vertical gap between
 * successive layers (TAD §2.5). No PRD basis (see docs/adr/0003). */
const LAYER_SPACING_PX = 80;
/** ELK's `elk.spacing.nodeNode` — gap between siblings within one layer
 * (TAD §2.5). No PRD basis (see docs/adr/0003). */
const NODE_SPACING_PX = 48;

const elk = new ELK();

/**
 * Shifts a freshly laid-out block of nodes down until it clears every
 * `obstacle` (D15's pinned nodes).
 *
 * ELK is only ever given the *unpinned* nodes, so it always lays them out
 * starting at its own origin — with no idea that a pinned card already
 * occupies that space. Without this pass, fanning out a node while any card
 * is pinned drops the new card straight on top of the pinned one. ELK's own
 * `elk.interactive` / `elk.position` options are not a substitute: they bias
 * ELK's ordering heuristics but do not hold a node at fixed coordinates
 * (verified — a node given `elk.position` still gets moved), and feeding
 * pinned nodes in as ordinary children would let ELK reposition them, which
 * D15 forbids.
 *
 * A single rigid vertical translation of the whole block (rather than
 * per-node nudging) is deliberate: it preserves ELK's layering exactly, so
 * the call-direction reading order the layout exists to produce survives.
 */
export function offsetPastObstacles(
  positions: LayoutPositions,
  sizes: Map<string, { width: number; height: number }>,
  obstacles: LayoutObstacle[],
): LayoutPositions {
  if (obstacles.length === 0) return positions;

  const entries = Object.entries(positions);
  if (entries.length === 0) return positions;

  let shift = 0;
  // Re-check after every shift: moving the block clear of one pinned card can
  // slide it into another, so keep pushing until a full pass is collision
  // free. Bounded by the obstacle count — each iteration clears at least one.
  for (let pass = 0; pass <= obstacles.length; pass += 1) {
    let worst = 0;
    for (const [id, pos] of entries) {
      const size = sizes.get(id);
      if (!size) continue;
      const top = pos.y + shift;
      const bottom = top + size.height;
      for (const obstacle of obstacles) {
        const overlapsX =
          pos.x < obstacle.x + obstacle.width && pos.x + size.width > obstacle.x;
        const overlapsY = top < obstacle.y + obstacle.height && bottom > obstacle.y;
        if (!overlapsX || !overlapsY) continue;
        // Push this node's top below the obstacle's bottom, plus the normal
        // inter-layer gap so the result reads like the rest of the layout.
        worst = Math.max(worst, obstacle.y + obstacle.height + LAYER_SPACING_PX - top);
      }
    }
    if (worst <= 0) break;
    shift += worst;
  }

  if (shift === 0) return positions;
  const shifted: LayoutPositions = {};
  for (const [id, pos] of entries) {
    shifted[id] = { x: pos.x, y: pos.y + shift };
  }
  return shifted;
}

export async function computeElkLayout(
  nodes: LayoutInputNode[],
  edges: LayoutInputEdge[],
  obstacles: LayoutObstacle[] = [],
): Promise<LayoutPositions> {
  const graph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.layered.layering.strategy": "NETWORK_SIMPLEX",
      // §5.1: cycles must not explode — GREEDY cycle breaking handles
      // back-edges (recursion, mutual recursion) without pathological output.
      "elk.layered.cycleBreaking.strategy": "GREEDY",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      // NOTE the `layered.` prefix: `elk.spacing.nodeNodeBetweenLayers` is
      // NOT a real ELK option — the layered algorithm reads
      // `elk.layered.spacing.nodeNodeBetweenLayers`. Spelled without the
      // prefix, elkjs silently ignores it and falls back to its own default
      // (20px), which is far too tight for cards that are hundreds of px
      // tall and reads as "the gap is broken".
      "elk.layered.spacing.nodeNodeBetweenLayers": String(LAYER_SPACING_PX),
      "elk.spacing.nodeNode": String(NODE_SPACING_PX),
    },
    children: nodes.map((n) => ({ id: n.id, width: n.width, height: n.height })),
    edges: edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  };

  try {
    const laidOut = await elk.layout(graph);
    const positions: LayoutPositions = {};
    for (const child of laidOut.children ?? []) {
      if (child.id && child.x !== undefined && child.y !== undefined) {
        positions[child.id] = { x: child.x, y: child.y };
      }
    }
    const sizes = new Map(nodes.map((n) => [n.id, { width: n.width, height: n.height }]));
    return offsetPastObstacles(positions, sizes, obstacles);
  } catch {
    // A failed layout is a no-op for the caller (nodes keep their current
    // positions) — never throw over one bad request.
    return {};
  }
}
