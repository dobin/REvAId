import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfigProvider } from "@/config/ConfigProvider";
import { CanvasView } from "./CanvasView";
import type { AppConfigDto, EntryPointsDto, FunctionDto, NeighbourPageDto, ViewSummaryDto } from "@/api/types";

const config: AppConfigDto = {
  tableRowCap: 16,
  callerSuppressThreshold: 32,
  utilityFanInThreshold: 50,
  fanOutAllHardCap: 50,
  nodeCountSoftWarning: 150,
  cardWidthPx: 380,
  summaryConcurrency: 4,
  nodeColorPalette: ["slate"],
  adapters: { ghidra: "mock", llm: "mock", llmModel: "mock-llm-v1" },
};

const entryPoints: EntryPointsDto = {
  entryPoints: [{ id: 1, address: 0x401000, displayName: "main", fanOut: 16, fanIn: 0 }],
};

const views: ViewSummaryDto[] = [
  {
    id: 5,
    binaryId: 1,
    name: "Default",
    rootFunctionId: null,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
  },
];

const mainFn: FunctionDto = {
  id: 1,
  binaryId: 1,
  address: 0x401000,
  displayName: "main",
  nameGhidra: "main",
  nameAnalyst: null,
  isRenamed: false,
  parameters: [],
  signature: null,
  kind: "normal",
  placeholderModule: null,
  fanIn: 0,
  fanOut: 16,
  isUtility: false,
  utilitySource: "computed",
  utilityOverride: null,
  summary: {
    status: "none",
    short: null,
    long: null,
    model: null,
    errorCode: null,
    lowConfidence: false,
    generatedAt: null,
    isStale: false,
  },
  notes: "",
  hasNotes: false,
  notesUpdatedAt: null,
  calleeCount: 16,
  callerCount: 0,
  hasIndirectCalls: false,
};

function emptyPage(direction: "callees" | "callers"): NeighbourPageDto {
  return {
    functionId: 1,
    direction,
    group: "primary",
    rows: [],
    total: 0,
    totalPrimary: 0,
    totalUtility: 0,
    limit: 16,
    offset: 0,
    callersSuppressed: false,
    mayBeIncomplete: false,
  };
}

function renderWithProviders(selectedBinaryId: number | null) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ConfigProvider fallback={<p>loading</p>}>
        <CanvasView selectedBinaryId={selectedBinaryId} />
      </ConfigProvider>
    </QueryClientProvider>,
  );
}

describe("CanvasView", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = input instanceof Request ? input.url : String(input);
        if (url.endsWith("/api/v1/config")) {
          return Promise.resolve(new Response(JSON.stringify(config), { status: 200 }));
        }
        if (url.endsWith("/api/v1/binaries/1/entry-points")) {
          return Promise.resolve(new Response(JSON.stringify(entryPoints), { status: 200 }));
        }
        if (url.endsWith("/api/v1/binaries/1/views")) {
          return Promise.resolve(new Response(JSON.stringify(views), { status: 200 }));
        }
        if (url.includes("/api/v1/functions/1/neighbours")) {
          const direction = url.includes("direction=callers") ? "callers" : "callees";
          return Promise.resolve(
            new Response(JSON.stringify(emptyPage(direction)), { status: 200 }),
          );
        }
        if (url.endsWith("/api/v1/functions/1")) {
          return Promise.resolve(new Response(JSON.stringify(mainFn), { status: 200 }));
        }
        return Promise.reject(new Error(`Unexpected fetch: ${url}`));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows an empty state when no binary is selected", async () => {
    renderWithProviders(null);
    await waitFor(() => {
      expect(screen.getByText(/pick a binary from the toolbar/i)).toBeInTheDocument();
    });
  });

  it("renders the top entry point's card once the binary, entry points, and view resolve", async () => {
    renderWithProviders(1);
    await waitFor(() => {
      expect(screen.getByText("main")).toBeInTheDocument();
    });
  });
});
