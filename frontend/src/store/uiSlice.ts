/**
 * Selection / detail-panel target (TAD §3.1: "Selection / detail-panel
 * target" — client session, lost on reload, never persisted).
 */
import type { StateCreator } from "zustand";
import type { FunctionId } from "@/api/types";

export interface UiSlice {
  selectedFunctionId: FunctionId | null;
  selectFunction: (functionId: FunctionId) => void;
  clearSelection: () => void;
}

export const createUiSlice: StateCreator<UiSlice, [], [], UiSlice> = (set) => ({
  selectedFunctionId: null,
  selectFunction: (functionId) => {
    set({ selectedFunctionId: functionId });
  },
  clearSelection: () => {
    set({ selectedFunctionId: null });
  },
});
