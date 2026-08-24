/**
 * I9 summary demand registry (TAD §5, PLAN-I7-I8-I9-I13 §5.2/AM6/AS36).
 *
 * Pure refcounting only — no network calls live here. `acquire`/`release`
 * report which function ids crossed the 0<->1 refcount boundary; the caller
 * (`hooks/useSummaryDemand.ts`) is the only thing that turns those
 * transitions into `POST`/`DELETE /functions/{id}/summary` calls. Keeping
 * this slice side-effect-free means its refcount arithmetic can be unit
 * tested without a QueryClient or mocked fetches.
 *
 * A "surface" is any mounted UI region that wants a function's summary kept
 * warm — a table row, a card's own summary, the detail panel. The same
 * function id is commonly demanded by several surfaces at once (it appears
 * in more than one card's callee/caller table); the id is only released once
 * every surface referencing it has released it (or unmounted via
 * `releaseSurface`).
 *
 * AS36 — single tab assumed. This registry is per-tab (per Zustand store
 * instance); two tabs against the same backend double-count demand. Accepted
 * per the plan; not handled here.
 */
import type { StateCreator } from "zustand";
import type { FunctionId } from "@/api/types";

/** Identifies one mounted UI region that can hold demand on function ids. */
export type SurfaceId = string;

export interface DemandChangeResult {
  /** Ids that went from 0 -> 1 references — the caller must now request them. */
  newlyDemanded: FunctionId[];
  /** Ids that went from 1 -> 0 references — the caller must now release them. */
  newlyReleased: FunctionId[];
}

export interface DemandSlice {
  /** function id -> set of surfaces currently holding demand on it. */
  demandRefs: Map<FunctionId, Set<SurfaceId>>;
  /**
   * Register `surface`'s interest in exactly `functionIds` (replacing
   * whatever that surface previously held — callers pass their full current
   * set each time, e.g. the virtualizer's visible+overscan window).
   */
  acquireDemand: (functionIds: readonly FunctionId[], surface: SurfaceId) => DemandChangeResult;
  /** Drop every id `surface` currently holds (unmount / collapse / hide). */
  releaseSurface: (surface: SurfaceId) => DemandChangeResult;
}

export const createDemandSlice: StateCreator<DemandSlice, [], [], DemandSlice> = (set, get) => ({
  demandRefs: new Map(),

  acquireDemand: (functionIds, surface) => {
    const next = new Map(get().demandRefs);
    const wanted = new Set(functionIds);
    const newlyDemanded: FunctionId[] = [];
    const newlyReleased: FunctionId[] = [];

    // Drop `surface` from any id it previously held but no longer wants.
    for (const [id, surfaces] of next) {
      if (surfaces.has(surface) && !wanted.has(id)) {
        const updated = new Set(surfaces);
        updated.delete(surface);
        if (updated.size === 0) {
          next.delete(id);
          newlyReleased.push(id);
        } else {
          next.set(id, updated);
        }
      }
    }

    // Add `surface` to every id it now wants.
    for (const id of wanted) {
      const existing = next.get(id);
      if (existing) {
        if (!existing.has(surface)) {
          const updated = new Set(existing);
          updated.add(surface);
          next.set(id, updated);
        }
      } else {
        next.set(id, new Set([surface]));
        newlyDemanded.push(id);
      }
    }

    set({ demandRefs: next });
    return { newlyDemanded, newlyReleased };
  },

  releaseSurface: (surface) => {
    const next = new Map(get().demandRefs);
    const newlyReleased: FunctionId[] = [];

    for (const [id, surfaces] of next) {
      if (!surfaces.has(surface)) continue;
      const updated = new Set(surfaces);
      updated.delete(surface);
      if (updated.size === 0) {
        next.delete(id);
        newlyReleased.push(id);
      } else {
        next.set(id, updated);
      }
    }

    set({ demandRefs: next });
    return { newlyDemanded: [], newlyReleased };
  },
});
