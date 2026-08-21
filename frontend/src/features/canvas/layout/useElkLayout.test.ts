import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useElkLayout, type ElkWorkerFactory } from "./useElkLayout";
import type { LayoutRequest, LayoutResponse } from "./elk.worker";

/** A fake worker that records every posted request and lets the test decide
 * when/whether to reply, so latest-wins and pinned-exclusion can be
 * asserted deterministically without a real ELK computation. */
function makeFakeWorker() {
  const posted: LayoutRequest[] = [];
  let onmessage: ((event: MessageEvent<LayoutResponse>) => void) | null = null;
  const worker = {
    postMessage: (request: LayoutRequest) => {
      posted.push(request);
    },
    terminate: vi.fn(),
    set onmessage(handler: ((event: MessageEvent<LayoutResponse>) => void) | null) {
      onmessage = handler;
    },
    get onmessage() {
      return onmessage;
    },
  } as unknown as Worker;

  return {
    worker,
    posted,
    reply: (response: LayoutResponse) => {
      onmessage?.({ data: response } as MessageEvent<LayoutResponse>);
    },
  };
}

describe("useElkLayout", () => {
  it("excludes pinned nodes and their edges from the ELK request", () => {
    const fake = makeFakeWorker();
    const factory: ElkWorkerFactory = () => fake.worker;
    const { result } = renderHook(() => useElkLayout(factory));

    act(() => {
      result.current.runLayout(
        [
          { id: "1", width: 380, height: 200, pinned: true },
          { id: "2", width: 380, height: 200, pinned: false },
        ],
        [{ id: "1->2", source: "1", target: "2" }],
      );
    });

    expect(fake.posted).toHaveLength(1);
    expect(fake.posted[0]?.nodes).toEqual([{ id: "2", width: 380, height: 200 }]);
    expect(fake.posted[0]?.edges).toEqual([]);
  });

  it("latest-wins: a stale response for a superseded request is ignored", () => {
    const fake = makeFakeWorker();
    const factory: ElkWorkerFactory = () => fake.worker;
    const { result } = renderHook(() => useElkLayout(factory));

    act(() => {
      result.current.runLayout([{ id: "1", width: 380, height: 200, pinned: false }], []);
    });
    const firstRequestId = fake.posted[0]?.requestId;
    if (firstRequestId === undefined) throw new Error("expected a posted request");

    act(() => {
      result.current.runLayout([{ id: "2", width: 380, height: 200, pinned: false }], []);
    });
    const secondRequestId = fake.posted[1]?.requestId;
    if (secondRequestId === undefined) throw new Error("expected a posted request");
    expect(secondRequestId).not.toBe(firstRequestId);

    // The stale first request resolves after the second was issued.
    act(() => {
      fake.reply({ requestId: firstRequestId, positions: { "1": { x: 999, y: 999 } } });
    });
    expect(result.current.positions).toEqual({});

    act(() => {
      fake.reply({ requestId: secondRequestId, positions: { "2": { x: 10, y: 20 } } });
    });
    expect(result.current.positions).toEqual({ "2": { x: 10, y: 20 } });
  });
});
