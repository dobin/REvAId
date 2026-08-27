import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/api/client";
import type {
  FunctionSearchPageDto,
  NeighbourPageDto,
  NeighbourRowDto,
  ViewNodesPatchResponse,
} from "@/api/types";
import { CanvasActionsProvider, type CanvasActions } from "@/features/canvas/CanvasActions";
import { FunctionSearchInput } from "./FunctionSearchInput";

function neighbourRow(overrides: Partial<NeighbourRowDto> & { id: number }): NeighbourRowDto {
  return {
    id: overrides.id,
    address: 0x402000,
    displayName: `fn_${String(overrides.id)}`,
    nameLlm: null,
    isRenamed: false,
    summaryShort: null,
    summaryStatus: "none",
    summaryLowConfidence: false,
    kind: "normal",
    onCanvas: false,
    isUtility: false,
    utilitySource: "computed",
    fanIn: 1,
    isSelf: false,
    hasNotes: false,
    ...overrides,
  };
}

function neighbourPage(
  direction: "callees" | "callers",
  rows: NeighbourRowDto[],
): NeighbourPageDto {
  return {
    functionId: 7,
    direction,
    group: "primary",
    rows,
    total: rows.length,
    totalPrimary: rows.length,
    totalUtility: 0,
    limit: 16,
    offset: 0,
    callersSuppressed: false,
    mayBeIncomplete: false,
  };
}

function renderInput(
  binaryId: number | null = 1,
  viewId: number | null = 1,
  runtimeBase: number | null = null,
  analysisImageBase: number | null = 0x180000000,
  canvasActions: CanvasActions | null = null,
) {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <CanvasActionsProvider value={canvasActions}>
        <FunctionSearchInput
          binaryId={binaryId}
          viewId={viewId}
          runtimeBase={runtimeBase}
          analysisImageBase={analysisImageBase}
        />
      </CanvasActionsProvider>
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
    expect(getSpy).toHaveBeenCalledWith("/views/1");
    expect(getSpy).not.toHaveBeenCalledWith(expect.stringContaining("/functions?"));
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

  it("auto-links to an on-canvas caller (grows right, fanout)", async () => {
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
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url.includes("/neighbours")) {
        // function 7 is called by on-canvas function 3.
        return Promise.resolve(
          url.includes("direction=callers")
            ? neighbourPage("callers", [neighbourRow({ id: 3, onCanvas: true })])
            : neighbourPage("callees", []),
        );
      }
      return Promise.resolve(page);
    });
    const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue({ nodes: [] });

    renderInput();
    fireEvent.change(screen.getByLabelText("Search functions"), { target: { value: "parse" } });
    fireEvent.click(await screen.findByText("parse_config"));

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/views/1/nodes", {
        upsert: [
          {
            functionId: 7,
            visible: true,
            originFunctionId: 3,
            originKind: "fanout",
            originImplied: false,
          },
        ],
      });
    });
  });

  it("auto-links to an on-canvas callee when no caller is present (fanin)", async () => {
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
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url.includes("/neighbours")) {
        // function 7 calls on-canvas function 9; no caller is on canvas.
        return Promise.resolve(
          url.includes("direction=callers")
            ? neighbourPage("callers", [])
            : neighbourPage("callees", [neighbourRow({ id: 9, onCanvas: true })]),
        );
      }
      return Promise.resolve(page);
    });
    const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue({ nodes: [] });

    renderInput();
    fireEvent.change(screen.getByLabelText("Search functions"), { target: { value: "parse" } });
    fireEvent.click(await screen.findByText("parse_config"));

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/views/1/nodes", {
        upsert: [
          {
            functionId: 7,
            visible: true,
            originFunctionId: 9,
            originKind: "fanin",
            originImplied: false,
          },
        ],
      });
    });
  });

  it("falls back to a root node when nothing on canvas is connected", async () => {
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
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url.includes("/neighbours")) {
        return Promise.resolve(
          url.includes("direction=callers")
            ? neighbourPage("callers", [neighbourRow({ id: 3, onCanvas: false })])
            : neighbourPage("callees", [neighbourRow({ id: 9, onCanvas: false })]),
        );
      }
      return Promise.resolve(page);
    });
    const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue({ nodes: [] });

    renderInput();
    fireEvent.change(screen.getByLabelText("Search functions"), { target: { value: "parse" } });
    fireEvent.click(await screen.findByText("parse_config"));

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith("/views/1/nodes", {
        upsert: [{ functionId: 7, visible: true, originKind: "root" }],
      });
    });
  });

  it("jumps to an already-visible function instead of adding it again", async () => {
    const page: FunctionSearchPageDto = {
      rows: [{
        id: 7,
        address: 0x401000,
        displayName: "parse_config",
        isRenamed: false,
        kind: "normal",
        isUtility: false,
        fanIn: 2,
        hasNotes: false,
        isEntryPoint: false,
      }],
      total: 1,
      limit: 50,
      offset: 0,
      query: "parse",
    };
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url === "/views/1") {
        return Promise.resolve({ nodes: [{ functionId: 7, visible: true }] });
      }
      return Promise.resolve(page);
    });
    const patchSpy = vi.spyOn(apiClient, "patch");
    const focusFunction = vi.fn();

    renderInput(1, 1, null, 0x180000000, {
      fanOutFunction: vi.fn(),
      focusFunction,
      hideFunction: vi.fn(),
    });
    fireEvent.change(screen.getByLabelText("Search functions"), { target: { value: "parse" } });
    fireEvent.click(await screen.findByText("parse_config"));

    expect(focusFunction).toHaveBeenCalledWith(7);
    expect(patchSpy).not.toHaveBeenCalled();
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
    expect(getSpy).toHaveBeenCalledWith("/views/1");
    expect(getSpy).not.toHaveBeenCalledWith(expect.stringContaining("/functions"));
  });
});
