/**
 * Canvas/session state (TAD §3.1) — node positions and pin state, keyed by
 * `functionId`. This is the "in-flight drag delta" + `pinned` cell of the
 * TAD's state-ownership matrix: authoritative values live in `view_nodes`
 * (fetched via `useViewQuery`), but drag needs a 60fps-safe local mirror
 * that does not round-trip through TanStack Query on every frame.
 *
 * Deliberately excludes anything ephemeral (`tableUiSlice`-style filter/sort
 * state) and anything server-durable that isn't position/pin — colour,
 * visibility, and collapse are patched directly via `usePatchViewNodesMutation`
 * and read from the `ViewDto` cache, not mirrored here.
 */
import type { StateCreator } from "zustand";
import type { FunctionId, ViewNodeDto } from "@/api/types";

export interface CanvasNodePosition {
  posX: number;
  posY: number;
  pinned: boolean;
  /** True only while a drag gesture is in progress on this node. */
  dragging: boolean;
}

export interface CanvasSlice {
  positions: Record<FunctionId, CanvasNodePosition>;
  /** Replace all known positions from a freshly-fetched view (page load,
   * view switch). Never merges — a view switch must not inherit stale
   * positions from a previous view (D8a-adjacent: state is reset, not
   * carried over). */
  hydrateFromView: (nodes: ViewNodeDto[]) => void;
  /** Called on every drag-move frame — local only, never persisted. */
  setDragPosition: (functionId: FunctionId, posX: number, posY: number) => void;
  /** Called once on drag end (`onNodeDragStop`): marks the node pinned and
   * finalizes its position. The caller is responsible for persisting this
   * via `usePatchViewNodesMutation` — this slice only holds client state. */
  commitDragAsPinned: (functionId: FunctionId, posX: number, posY: number) => void;
  /** Optimistic local insert for a freshly fanned-out node (D8a: gets
   * defaults, not inherited state) — unpinned, so the next ELK layout
   * pass positions it properly once the server round trip lands. */
  upsertPosition: (functionId: FunctionId, posX: number, posY: number, pinned: boolean) => void;
  /** Wipe all local position state — call after a full canvas reset so
   * stale pinned/dragging entries do not bleed into the blank canvas. */
  clearPositions: () => void;
  /** Unpin every node so the next ELK layout pass repositions them all from
   * scratch (rebalance / "forget manual moves"). Does not touch the server —
   * the caller must persist the change via `usePatchViewNodesMutation`. */
  unpinAll: () => void;
}

export const createCanvasSlice: StateCreator<CanvasSlice, [], [], CanvasSlice> = (set) => ({
  positions: {},
  hydrateFromView: (nodes) => {
    const positions: Record<FunctionId, CanvasNodePosition> = {};
    for (const node of nodes) {
      positions[node.functionId] = {
        posX: node.posX,
        posY: node.posY,
        pinned: node.pinned,
        dragging: false,
      };
    }
    set({ positions });
  },
  setDragPosition: (functionId, posX, posY) => {
    set((state) => ({
      positions: {
        ...state.positions,
        [functionId]: {
          ...(state.positions[functionId] ?? { pinned: false, dragging: false, posX, posY }),
          posX,
          posY,
          dragging: true,
        },
      },
    }));
  },
  commitDragAsPinned: (functionId, posX, posY) => {
    set((state) => ({
      positions: {
        ...state.positions,
        [functionId]: { posX, posY, pinned: true, dragging: false },
      },
    }));
  },
  upsertPosition: (functionId, posX, posY, pinned) => {
    set((state) => ({
      positions: {
        ...state.positions,
        [functionId]: { posX, posY, pinned, dragging: false },
      },
    }));
  },
  clearPositions: () => set({ positions: {} }),
  unpinAll: () =>
    set((state) => {
      const updated: Record<FunctionId, CanvasNodePosition> = {};
      for (const [id, pos] of Object.entries(state.positions)) {
        updated[id as FunctionId] = { ...pos, pinned: false, dragging: false };
      }
      return { positions: updated };
    }),
});
