/**
 * Canvas action context (I6) — bridges `NeighbourRow`'s fan-out/focus click
 * and `OnCanvasList`'s focus click into the actual canvas surface, without
 * prop-drilling `viewId`/`useReactFlow()` through every card's neighbour
 * tables. Provided by `CanvasView`; consumed by anything that needs to
 * promote a function onto the canvas or pan to an existing node.
 */
import { createContext, useContext } from "react";
import type { FunctionId } from "@/api/types";

export interface CanvasActions {
  /** Promote `functionId` onto the canvas, with provenance pointing back at
   * `originFunctionId` (D8/D8b). No-op if the function is already on the
   * canvas — callers should prefer {@link focusFunction} in that case. */
  fanOutFunction: (originFunctionId: FunctionId, functionId: FunctionId) => void;
  /** Pan/center the canvas on an already-placed node (D9's ◎ affordance). */
  focusFunction: (functionId: FunctionId) => void;
}

const CanvasActionsContext = createContext<CanvasActions | null>(null);

export const CanvasActionsProvider = CanvasActionsContext.Provider;

/** Returns `null` outside a `CanvasView` (e.g. in isolated component tests)
 * rather than throwing — callers render inert controls in that case. */
export function useCanvasActions(): CanvasActions | null {
  return useContext(CanvasActionsContext);
}
