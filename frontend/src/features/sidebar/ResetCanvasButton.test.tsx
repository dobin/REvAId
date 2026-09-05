import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { apiClient } from "@/api/client";
import type { EntryPointsDto, ViewDto } from "@/api/types";
import { ResetCanvasButton } from "./ResetCanvasButton";

const view: ViewDto = {
  id: 5,
  binaryId: 1,
  name: "Default",
  rootFunctionId: 42,
  camera: { x: 0, y: 0, zoom: 1 },
  nodes: [
    {
      functionId: 42,
      visible: true,
      collapsed: false,
      color: null,
      posX: 0,
      posY: 0,
      pinned: false,
      originFunctionId: null,
      originKind: "root",
      originImplied: false,
    },
    {
      functionId: 7,
      visible: true,
      collapsed: false,
      color: null,
      posX: 20,
      posY: 20,
      pinned: false,
      originFunctionId: 42,
      originKind: "fanout",
      originImplied: false,
    },
  ],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const entryPoints: EntryPointsDto = {
  entryPoints: [{ id: 42, address: 0x401000, displayName: "main", fanOut: 4, fanIn: 0 }],
};

afterEach(() => {
  vi.restoreAllMocks();
});

it("removes all nodes before putting the entry point back", async () => {
  const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue({ nodes: [] });
  vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
    if (url === "/views/5") return Promise.resolve(view);
    if (url === "/binaries/1/entry-points") return Promise.resolve(entryPoints);
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ResetCanvasButton binaryId={1} viewId={5} />
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByRole("button", { name: /reset canvas/i }));

  await waitFor(() => {
    expect(patchSpy).toHaveBeenNthCalledWith(1, "/views/5/nodes", { remove: [42, 7] });
  });
  await waitFor(() => {
    expect(patchSpy).toHaveBeenNthCalledWith(2, "/views/5/nodes", {
      upsert: [{ functionId: 42, visible: true, originKind: "root" }],
    });
  });
});