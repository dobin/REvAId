import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/api/client";
import type { FunctionSearchPageDto, ViewNodesPatchResponse } from "@/api/types";
import { FunctionSearchInput } from "./FunctionSearchInput";

function renderInput(
  binaryId: number | null = 1,
  viewId: number | null = 1,
  runtimeBase: number | null = null,
  analysisImageBase: number | null = 0x180000000,
) {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <FunctionSearchInput
        binaryId={binaryId}
        viewId={viewId}
        runtimeBase={runtimeBase}
        analysisImageBase={analysisImageBase}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FunctionSearchInput", () => {
  it("searches functions and lists matches by name/address", async () => {
    const page: FunctionSearchPageDto = {
      rows: [
        {
          id: 7,
          address: 0x401000,
          displayName: "parse_config",
          isRenamed: false,
          kind: "normal",
          isUtility: false,
          fanIn: 2,
          hasNotes: false,
          isEntryPoint: false,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
      query: "parse",
    };
    const getSpy = vi.spyOn(apiClient, "get").mockResolvedValue(page);

    renderInput();
    fireEvent.change(screen.getByLabelText("Search functions"), { target: { value: "parse" } });

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalled();
    });
    expect(await screen.findByText("parse_config")).toBeInTheDocument();
    expect(screen.getByText("0x401000")).toBeInTheDocument();
  });

  it("adds the selected function to the canvas on click", async () => {
    const page: FunctionSearchPageDto = {
      rows: [
        {
          id: 7,
          address: 0x401000,
          displayName: "parse_config",
          isRenamed: false,
          kind: "normal",
          isUtility: false,
          fanIn: 2,
          hasNotes: false,
          isEntryPoint: false,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
      query: "parse",
    };
    vi.spyOn(apiClient, "get").mockResolvedValue(page);
    const patchResponse: ViewNodesPatchResponse = { nodes: [] };
    const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue(patchResponse);

    renderInput();
    fireEvent.change(screen.getByLabelText("Search functions"), { target: { value: "parse" } });
    fireEvent.click(await screen.findByText("parse_config"));

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/views/1/nodes", {
        upsert: [{ functionId: 7, visible: true, originKind: "root" }],
      });
    });
  });

  it("does not fetch when the query is empty", () => {
    const getSpy = vi.spyOn(apiClient, "get").mockResolvedValue({
      rows: [],
      total: 0,
      limit: 50,
      offset: 0,
      query: null,
    });
    renderInput();
    expect(getSpy).not.toHaveBeenCalled();
  });

  it("translates a runtime VA before resolving and adding its function", async () => {
    const resolved = {
      id: 7,
      address: 0x180a4cb90,
      displayName: "parse_config",
    };
    const getSpy = vi.spyOn(apiClient, "get").mockResolvedValue(resolved);
    const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue({ nodes: [] });

    renderInput(1, 1, 0x7ffeefb40000, 0x168d7b8cc);
    fireEvent.change(screen.getByLabelText("Search functions"), {
      target: { value: "0x7fff078112c4" },
    });

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith(
        "/binaries/1/functions/by-address?address=0x180a4cb90",
      );
    });
    fireEvent.click(await screen.findByText("parse_config"));
    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/views/1/nodes", {
        upsert: [{ functionId: 7, visible: true, originKind: "root" }],
      });
    });
  });

  it("requires a recorded Ghidra base for runtime address lookup", async () => {
    const getSpy = vi.spyOn(apiClient, "get");
    renderInput(1, 1, 0x7ffeefb40000, null);
    fireEvent.change(screen.getByLabelText("Search functions"), {
      target: { value: "0x7fff078112c4" },
    });

    expect(
      await screen.findByText(/re-export and re-ingest/i),
    ).toBeInTheDocument();
    expect(getSpy).not.toHaveBeenCalled();
  });
});
