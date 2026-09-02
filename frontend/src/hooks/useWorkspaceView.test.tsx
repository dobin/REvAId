/**
 * ADR 0006: workspace view resolution — private mode defaults to the
 * binary's first view; public mode resolves/creates this browser's own
 * anonymous view and never falls back to a shared one.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import { apiClient } from "@/api/client";
import type { ViewDto, ViewSummaryDto } from "@/api/types";
import { getMyViews, recordMyView } from "@/lib/myViews";
import { useWorkspaceView } from "./useWorkspaceView";

// The hook reads the mode from useConfig(); mocking the provider keeps
// these tests independent of the fetch-backed ConfigProvider.
const configMock = vi.hoisted(() => ({ publicMode: false }));
vi.mock("@/config/ConfigProvider", () => ({
  useConfig: () => configMock,
}));

const views: ViewSummaryDto[] = [
  {
    id: 5,
    binaryId: 1,
    name: "Default",
    rootFunctionId: null,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
  },
  {
    id: 6,
    binaryId: 1,
    name: "Owner's analysis",
    rootFunctionId: null,
    createdAt: "2026-01-02T00:00:00Z",
    updatedAt: "2026-01-02T00:00:00Z",
  },
];

const createdView: ViewDto = {
  id: 42,
  binaryId: 1,
  name: "My view",
  rootFunctionId: null,
  camera: { x: 0, y: 0, zoom: 1 },
  nodes: [],
  createdAt: "2026-01-03T00:00:00Z",
  updatedAt: "2026-01-03T00:00:00Z",
};

function makeWrapper() {
  const queryClient = new QueryClient();
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ) as ReactElement;
  return { queryClient, wrapper };
}

function seedViews(queryClient: QueryClient): void {
  queryClient.setQueryData(["views", 1], views);
}

describe("useWorkspaceView", () => {
  beforeEach(() => {
    window.localStorage.clear();
    configMock.publicMode = false;
  });
  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("private mode: defaults to the binary's first view", async () => {
    const { queryClient, wrapper } = makeWrapper();
    seedViews(queryClient);

    const { result } = renderHook(() => useWorkspaceView(1), { wrapper });
    await waitFor(() => {
      expect(result.current.viewId).toBe(5);
    });
    expect(result.current.isResolving).toBe(false);
  });

  it("private mode: an explicit selection wins over the default", async () => {
    const { queryClient, wrapper } = makeWrapper();
    seedViews(queryClient);

    const { result } = renderHook(() => useWorkspaceView(1), { wrapper });
    await waitFor(() => {
      expect(result.current.viewId).toBe(5);
    });

    act(() => {
      result.current.selectView(6);
    });
    expect(result.current.viewId).toBe(6);
  });

  it("public mode: creates a fresh view on first visit and records it", async () => {
    configMock.publicMode = true;
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue(createdView);
    const getSpy = vi.spyOn(apiClient, "get");
    const { queryClient, wrapper } = makeWrapper();
    seedViews(queryClient);

    const { result } = renderHook(() => useWorkspaceView(1), { wrapper });
    expect(result.current.isResolving).toBe(true);

    await waitFor(() => {
      expect(result.current.viewId).toBe(42);
    });
    expect(postSpy).toHaveBeenCalledWith("/binaries/1/views", { name: "My view" });
    // The created view is now this browser's owned view, with its name.
    expect(getMyViews(1)).toEqual([{ id: 42, name: "My view" }]);
    // No listing fetch in public mode — the endpoint is closed.
    expect(getSpy).not.toHaveBeenCalledWith("/binaries/1/views");
  });

  it("public mode: reuses the browser's owned view on a later visit", async () => {
    configMock.publicMode = true;
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue(createdView);
    recordMyView(1, 42, "My view");
    const { wrapper } = makeWrapper();

    const { result } = renderHook(() => useWorkspaceView(1), { wrapper });
    await waitFor(() => {
      expect(result.current.viewId).toBe(42);
    });
    // Never created a second view, never touched the shared ones.
    expect(postSpy).not.toHaveBeenCalled();
  });

  it("public mode: never falls back to the binary's shared first view", async () => {
    configMock.publicMode = true;
    vi.spyOn(apiClient, "post").mockResolvedValue(createdView);
    const { queryClient, wrapper } = makeWrapper();
    seedViews(queryClient);

    const { result } = renderHook(() => useWorkspaceView(1), { wrapper });
    await waitFor(() => {
      expect(result.current.viewId).toBe(42);
    });
    expect(result.current.viewId).not.toBe(5);
    expect(result.current.viewId).not.toBe(6);
  });

  it("resets the selection when the binary changes", async () => {
    const { queryClient, wrapper } = makeWrapper();
    seedViews(queryClient);

    const { result, rerender } = renderHook(({ binaryId }) => useWorkspaceView(binaryId), {
      wrapper,
      initialProps: { binaryId: 1 },
    });
    await waitFor(() => {
      expect(result.current.viewId).toBe(5);
    });

    rerender({ binaryId: 2 });
    // Resolving again — binary 2 has no views seeded and private mode waits
    // for the listing rather than leaking binary 1's view id.
    expect(result.current.viewId).toBeNull();
    expect(result.current.isResolving).toBe(true);
  });
});
