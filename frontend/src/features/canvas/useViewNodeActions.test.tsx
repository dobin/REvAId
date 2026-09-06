import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ViewDto, ViewNodeDto } from "@/api/types";
import { useViewNodeActions } from "./useViewNodeActions";

function node(
  functionId: number,
  originFunctionId: number | null,
  originKind: ViewNodeDto["originKind"],
  visible = true,
): ViewNodeDto {
  return {
    functionId,
    visible,
    collapsed: false,
    color: null,
    posX: 0,
    posY: 0,
    pinned: false,
    originFunctionId,
    originKind,
    originImplied: false,
  };
}

function view(nodes: ViewNodeDto[]): ViewDto {
  return {
    id: 1,
    binaryId: 1,
    name: "Test view",
    rootFunctionId: 1,
    camera: { x: 0, y: 0, zoom: 1 },
    nodes,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
  };
}

function wrapperFor(queryClient: QueryClient) {
  return function QueryClientWrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useViewNodeActions", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps callees visible when closing a left-most card without shown callers", async () => {
    const currentView = view([
      node(1, null, "root"),
      node(2, 1, "fanout"),
      node(3, 2, "callstack"),
    ]);
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify({ nodes: currentView.nodes }), { status: 200 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    const queryClient = new QueryClient();
    queryClient.setQueryData(["view", 1], currentView);
    const { result } = renderHook(() => useViewNodeActions(1), {
      wrapper: wrapperFor(queryClient),
    });

    act(() => {
      result.current.setVisible(1, false);
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/views/1/nodes",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ upsert: [{ functionId: 1, visible: false }] }),
      }),
    );
  });

  it("closes the callee subtree when the card has a shown caller", async () => {
    const currentView = view([
      node(1, null, "root"),
      node(2, 1, "fanout"),
      node(3, 2, "callstack"),
      node(4, 1, "fanin"),
    ]);
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify({ nodes: currentView.nodes }), { status: 200 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    const queryClient = new QueryClient();
    queryClient.setQueryData(["view", 1], currentView);
    const { result } = renderHook(() => useViewNodeActions(1), {
      wrapper: wrapperFor(queryClient),
    });

    act(() => {
      result.current.setVisible(1, false);
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/views/1/nodes",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          upsert: [
            { functionId: 1, visible: false },
            { functionId: 2, visible: false },
            { functionId: 3, visible: false },
          ],
        }),
      }),
    );
  });
});
