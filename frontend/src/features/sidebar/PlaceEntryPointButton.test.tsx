import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/api/client";
import type { EntryPointsDto, ViewDto } from "@/api/types";
import { AutoPlaceEntryPoint, PlaceEntryPointButton } from "./PlaceEntryPointButton";

const entryPoints: EntryPointsDto = {
  entryPoints: [{ id: 42, address: 0x401000, displayName: "main", fanOut: 4, fanIn: 0 }],
};

const emptyView: ViewDto = {
  id: 5,
  binaryId: 1,
  name: "Default",
  rootFunctionId: null,
  camera: { x: 0, y: 0, zoom: 1 },
  nodes: [],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

function renderWithClient(node: React.ReactNode) {
  render(<QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("entry-point placement", () => {
  it("automatically adds the entry point to an initially empty view", async () => {
    const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue({ nodes: [] });
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url === "/views/5") return Promise.resolve(emptyView);
      if (url === "/binaries/1/entry-points") return Promise.resolve(entryPoints);
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithClient(<AutoPlaceEntryPoint binaryId={1} viewId={5} />);

    await waitFor(() => {
      expect(patchSpy).toHaveBeenNthCalledWith(1, "/views/5/nodes", {
        upsert: [{ functionId: 42, visible: true, originKind: "root" }],
      });
    });
    await waitFor(() => {
      expect(patchSpy).toHaveBeenNthCalledWith(2, "/views/5", { rootFunctionId: 42 });
    });
    expect(patchSpy).toHaveBeenCalledTimes(2);
  });

  it("places the entry point when requested manually", async () => {
    const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue({ nodes: [] });
    vi.spyOn(apiClient, "get").mockResolvedValue(entryPoints);

    renderWithClient(<PlaceEntryPointButton binaryId={1} viewId={5} />);
    fireEvent.click(await screen.findByRole("button", { name: /place entry point/i }));

    await waitFor(() => {
      expect(patchSpy).toHaveBeenNthCalledWith(1, "/views/5/nodes", {
        upsert: [{ functionId: 42, visible: true, originKind: "root" }],
      });
    });
  });
});