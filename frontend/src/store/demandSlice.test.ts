import { describe, expect, it } from "vitest";
import { create } from "zustand";
import { createDemandSlice, type DemandSlice } from "./demandSlice";

function makeStore() {
  return create<DemandSlice>()((...a) => createDemandSlice(...a));
}

describe("demandSlice", () => {
  it("acquiring new ids for a fresh surface reports them all as newly demanded", () => {
    const store = makeStore();
    const result = store.getState().acquireDemand([1, 2, 3], "surface-a");
    expect(result.newlyDemanded.sort()).toEqual([1, 2, 3]);
    expect(result.newlyReleased).toEqual([]);
  });

  it("a second surface referencing the same id does not re-demand it", () => {
    const store = makeStore();
    store.getState().acquireDemand([1], "surface-a");
    const result = store.getState().acquireDemand([1], "surface-b");
    expect(result.newlyDemanded).toEqual([]);
    expect(result.newlyReleased).toEqual([]);
  });

  it("releasing one of two surfaces holding an id keeps it demanded", () => {
    const store = makeStore();
    store.getState().acquireDemand([1], "surface-a");
    store.getState().acquireDemand([1], "surface-b");
    const result = store.getState().acquireDemand([], "surface-a");
    expect(result.newlyReleased).toEqual([]);
    expect(store.getState().demandRefs.get(1)?.has("surface-b")).toBe(true);
  });

  it("releasing the last surface holding an id reports it as newly released", () => {
    const store = makeStore();
    store.getState().acquireDemand([1], "surface-a");
    const result = store.getState().acquireDemand([], "surface-a");
    expect(result.newlyReleased).toEqual([1]);
    expect(store.getState().demandRefs.has(1)).toBe(false);
  });

  it("re-acquiring a shrunk set releases only the dropped ids", () => {
    const store = makeStore();
    store.getState().acquireDemand([1, 2, 3], "surface-a");
    const result = store.getState().acquireDemand([2], "surface-a");
    expect(result.newlyReleased.sort()).toEqual([1, 3]);
    expect(result.newlyDemanded).toEqual([]);
    expect(store.getState().demandRefs.has(2)).toBe(true);
  });

  it("releaseSurface drops every id the surface held, refcounting correctly", () => {
    const store = makeStore();
    store.getState().acquireDemand([1, 2], "surface-a");
    store.getState().acquireDemand([2], "surface-b");
    const result = store.getState().releaseSurface("surface-a");
    expect(result.newlyReleased.sort()).toEqual([1]);
    expect(store.getState().demandRefs.has(2)).toBe(true);
    expect(store.getState().demandRefs.has(1)).toBe(false);
  });

  it("releaseSurface on an unknown surface is a no-op", () => {
    const store = makeStore();
    store.getState().acquireDemand([1], "surface-a");
    const result = store.getState().releaseSurface("surface-unknown");
    expect(result.newlyReleased).toEqual([]);
    expect(store.getState().demandRefs.get(1)?.has("surface-a")).toBe(true);
  });
});
