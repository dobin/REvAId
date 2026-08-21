/**
 * Combined Zustand store (TAD §1.2/§3.1) — sliced per the TAD's directory
 * listing. Only `canvasSlice` + `uiSlice` exist in I6; `tableUiSlice`
 * (ephemeral filter/sort/collapse) and `demandSlice` (summary demand
 * refcounts) are deferred to I9/I10, when the features that need them land.
 */
import { create } from "zustand";
import { createCanvasSlice, type CanvasSlice } from "./canvasSlice";
import { createUiSlice, type UiSlice } from "./uiSlice";

export type AppStore = CanvasSlice & UiSlice;

export const useAppStore = create<AppStore>()((...a) => ({
  ...createCanvasSlice(...a),
  ...createUiSlice(...a),
}));
