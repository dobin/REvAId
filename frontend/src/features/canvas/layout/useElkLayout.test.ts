import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useElkLayout, type ElkLayoutFn } from "./useElkLayout";
import type {
  LayoutInputEdge,
  LayoutInputNode,
  LayoutObstacle,
  LayoutPositions,
} from "./elkLayout";

/** A controllable fake layout function that records every call and lets the
 * test decide when/whether to resolve, so latest-wins and pinned-exclusion
 * can be asserted deterministically without a real ELK computation. */
function makeFakeLayoutFn() {
  const calls: {
    nodes: LayoutInputNode[];
    edges: LayoutInputEdge[];
    obstacles: LayoutObstacle[] | undefined;
  }[] = [];
  const resolvers: ((positions: LayoutPositions) => void)[] = [];

  const fn: ElkLayoutFn = (nodes, edges, obstacles) => {
    calls.push({ nodes, edges, obstacles });
    return new Promise<LayoutPositions>((resolve) => {
      resolvers.push(resolve);
    });
  };

  return {
    fn,
    calls,
    resolve: (index: number, positions: LayoutPositions) => {
      resolvers[index]?.(positions);
    },
  };
}

describe("useElkLayout", () => {
  it("excludes pinned nodes and their edges from the ELK request", () => {
    const fake = makeFakeLayoutFn();
    const { result } = renderHook(() => useElkLayout(fake.fn));

    act(() => {
      result.current.runLayout(
        [
          { id: "1", width: 380, height: 200, pinned: true },
          { id: "2", width: 380, height: 200, pinned: false },
        ],
        [{ id: "1->2", source: "1", target: "2" }],
      );
    });

    expect(fake.calls).toHaveLength(1);
    expect(fake.calls[0]?.nodes).toEqual([{ id: "2", width: 380, height: 200 }]);
    expect(fake.calls[0]?.edges).toEqual([]);
  });

  it("passes each pinned node on as an obstacle so the block clears it", () => {
    const fake = makeFakeLayoutFn();
    const { result } = renderHook(() => useElkLayout(fake.fn));

    act(() => {
      result.current.runLayout(
        [
          { id: "1", width: 380, height: 546, pinned: true, x: 16, y: 24 },
          { id: "2", width: 380, height: 599, pinned: false, x: 0, y: 0 },
        ],
        [],
      );
    });

    // Withholding the pinned node from the graph is only half the job: its
    // rectangle still has to reach the layout call, or the unpinned block
    // gets laid out on top of it.
    expect(fake.calls[0]?.obstacles).toEqual([
      { x: 16, y: 24, width: 380, height: 546 },
    ]);
  });

  it("skips a pinned node whose position is unknown", () => {
    const fake = makeFakeLayoutFn();
    const { result } = renderHook(() => useElkLayout(fake.fn));

    act(() => {
      result.current.runLayout(
        [
          { id: "1", width: 380, height: 546, pinned: true },
          { id: "2", width: 380, height: 599, pinned: false },
        ],
        [],
      );
    });

    expect(fake.calls[0]?.obstacles).toEqual([]);
  });

  it("latest-wins: a stale result for a superseded call is ignored", async () => {
    const fake = makeFakeLayoutFn();
    const { result } = renderHook(() => useElkLayout(fake.fn));

    act(() => {
      result.current.runLayout([{ id: "1", width: 380, height: 200, pinned: false }], []);
    });
    act(() => {
      result.current.runLayout([{ id: "2", width: 380, height: 200, pinned: false }], []);
    });
    expect(fake.calls).toHaveLength(2);

    // The stale first call resolves after the second was issued.
    act(() => {
      fake.resolve(0, { "1": { x: 999, y: 999 } });
    });
    expect(result.current.positions).toEqual({});

    act(() => {
      fake.resolve(1, { "2": { x: 10, y: 20 } });
    });
    await waitFor(() => {
      expect(result.current.positions).toEqual({ "2": { x: 10, y: 20 } });
    });
  });

  it("calls the real elkjs implementation by default without throwing", async () => {
    const { result } = renderHook(() => useElkLayout());

    act(() => {
      result.current.runLayout(
        [
          { id: "1", width: 380, height: 200, pinned: false },
          { id: "2", width: 380, height: 200, pinned: false },
        ],
        [{ id: "1->2", source: "1", target: "2" }],
      );
    });

    await waitFor(() => {
      expect(Object.keys(result.current.positions)).toEqual(
        expect.arrayContaining(["1", "2"]),
      );
    });
  });
});
