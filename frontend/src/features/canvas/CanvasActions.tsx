/**
 * Canvas action context (I6) — bridges `NeighbourRow`'s fan-out/focus click
 * and `OnCanvasList`'s focus click into the actual canvas surface, without
 * prop-drilling `viewId`/`useReactFlow()` through every card's neighbour
 * tables. Provided by `CanvasView`; consumed by anything that needs to
 * promote a function onto the canvas or pan to an existing node.
 */
import { createContext, useContext, useRef, type RefObject } from "react";
import type { FunctionId } from "@/api/types";

/** Where a fanned-out row came from: the card whose table it sits in, plus
 * which of that card's tables (its callees, or its callers). `callers` grows
 * the canvas leftward (provenance kind `fanin`), `callees` rightward
 * (`fanout`). */
export interface FanOutOrigin {
  functionId: FunctionId;
  direction: "callees" | "callers";
}

export interface CanvasActions {
  /** Promote `functionId` onto the canvas, recording provenance back to
   * `origin.functionId` (D8/D8b). `origin.direction` decides orientation: a
   * `callers` row places the new node to the *left* of the origin card, a
   * `callees` row to the *right*. No-op if the function is already on the
   * canvas — callers should prefer {@link hideFunction} in that case. */
  fanOutFunction: (origin: FanOutOrigin, functionId: FunctionId) => void;
  /** Pan/center the canvas on an already-placed node (sidebar D9). */
  focusFunction: (functionId: FunctionId) => void;
  /** Hide (set visible:false) an already-placed node — toggling it off the
   * canvas from the neighbour row ◎ button. */
  hideFunction: (functionId: FunctionId) => void;
}

const CanvasActionsContext = createContext<CanvasActions | null>(null);

export const CanvasActionsProvider = CanvasActionsContext.Provider;

/** Returns `null` outside a `CanvasView` (e.g. in isolated component tests)
 * rather than throwing — callers render inert controls in that case. */
export function useCanvasActions(): CanvasActions | null {
  return useContext(CanvasActionsContext);
}

/**
 * A stable ref-based registry so components outside the `CanvasActionsProvider`
 * tree (e.g. the sidebar) can still call canvas actions. `CanvasViewInner`
 * writes its actions into this ref; consumers call through it.
 */
const CanvasActionsRegistryContext = createContext<RefObject<CanvasActions | null> | null>(null);

export const CanvasActionsRegistryProvider = CanvasActionsRegistryContext.Provider;

/** Creates the stable ref to pass to `CanvasActionsRegistryProvider`. */
export function useCreateCanvasActionsRegistry() {
  return useRef<CanvasActions | null>(null);
}

/** Reads canvas actions from the registry ref — works from anywhere inside
 * `CanvasActionsRegistryProvider`, including the sidebar. Falls back to the
 * direct context value (for tests / in-tree consumers). */
export function useCanvasActionsFromRegistry(): CanvasActions | null {
  const direct = useContext(CanvasActionsContext);
  const registry = useContext(CanvasActionsRegistryContext);
  return direct ?? registry?.current ?? null;
}
