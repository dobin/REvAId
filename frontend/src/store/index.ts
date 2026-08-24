/**
 * Combined Zustand store (TAD §1.2/§3.1) — sliced per the TAD's directory
 * listing. `canvasSlice` + `uiSlice` (I6) + `demandSlice` (I9, summary demand
 * refcounts). `tableUiSlice` (ephemeral filter/sort/collapse, AM6) is still
 * deferred — it belongs with whichever increment actually needs it.
 */
import { create } from "zustand";
import { createCanvasSlice, type CanvasSlice } from "./canvasSlice";
import { createDemandSlice, type DemandSlice } from "./demandSlice";
import { createUiSlice, type UiSlice } from "./uiSlice";

export type AppStore = CanvasSlice & UiSlice & DemandSlice;

export const useAppStore = create<AppStore>()((...a) => ({
  ...createCanvasSlice(...a),
  ...createUiSlice(...a),
  ...createDemandSlice(...a),
}));
