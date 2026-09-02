/**
 * ADR 0006: per-browser anonymous view ownership (`lib/myViews`).
 * jsdom provides a real `localStorage`, so these are true round-trip tests.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  forgetMyView,
  getLatestMyViewId,
  getMyViews,
  recordMyView,
} from "./myViews";

describe("myViews", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("returns no owned views for an unknown binary", () => {
    expect(getMyViews(1)).toEqual([]);
    expect(getLatestMyViewId(1)).toBeNull();
  });

  it("records and reorders owned views (id + name) per binary", () => {
    recordMyView(1, 10, "A");
    recordMyView(1, 11, "B");

    expect(getMyViews(1)).toEqual([
      { id: 10, name: "A" },
      { id: 11, name: "B" },
    ]);
    expect(getLatestMyViewId(1)).toBe(11);

    // Re-recording moves the id to the latest slot without duplicating, and
    // refreshes the stored name.
    recordMyView(1, 10, "A (renamed)");
    expect(getMyViews(1)).toEqual([
      { id: 11, name: "B" },
      { id: 10, name: "A (renamed)" },
    ]);
    expect(getLatestMyViewId(1)).toBe(10);
  });

  it("keeps binaries isolated from each other", () => {
    recordMyView(1, 10, "A");
    recordMyView(2, 99, "B");

    expect(getMyViews(1)).toEqual([{ id: 10, name: "A" }]);
    expect(getMyViews(2)).toEqual([{ id: 99, name: "B" }]);
  });

  it("forgets an owned view id", () => {
    recordMyView(1, 10, "A");
    recordMyView(1, 11, "B");
    forgetMyView(1, 10);

    expect(getMyViews(1)).toEqual([{ id: 11, name: "B" }]);
    expect(getLatestMyViewId(1)).toBe(11);
  });

  it("drops the binary entry entirely when its last view is forgotten", () => {
    recordMyView(1, 10, "A");
    forgetMyView(1, 10);

    expect(getMyViews(1)).toEqual([]);
    expect(getLatestMyViewId(1)).toBeNull();
  });

  it("degrades to empty when the stored payload is corrupt", () => {
    window.localStorage.setItem("graphrev.myViews.v2", "{not json");
    expect(getMyViews(1)).toEqual([]);

    window.localStorage.setItem(
      "graphrev.myViews.v2",
      JSON.stringify({ v: 1, views: null }),
    );
    expect(getMyViews(1)).toEqual([]);

    // Malformed entries (non-object / missing name / bad id) are filtered
    // out, well-formed ones kept.
    window.localStorage.setItem(
      "graphrev.myViews.v2",
      JSON.stringify({
        v: 2,
        views: {
          "1": [
            { id: 10, name: "ok" },
            { id: "oops", name: "bad id" },
            { name: "no id" },
            42,
            { id: 12, name: "also ok" },
          ],
        },
      }),
    );
    expect(getMyViews(1)).toEqual([
      { id: 10, name: "ok" },
      { id: 12, name: "also ok" },
    ]);
  });

  it("ignores a stale v1 payload entirely (no migration shim)", () => {
    window.localStorage.setItem(
      "graphrev.myViews.v1",
      JSON.stringify({ v: 1, views: { "1": [10, 11] } }),
    );
    expect(getMyViews(1)).toEqual([]);
  });
});
