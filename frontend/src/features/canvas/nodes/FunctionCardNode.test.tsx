import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactFlowProvider } from "@xyflow/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfigProvider } from "@/config/ConfigProvider";
import { FunctionCardNode } from "./FunctionCardNode";
import type { AppConfigDto, FunctionDto, NeighbourPageDto, ViewNodeDto } from "@/api/types";

const viewNode: ViewNodeDto = {
  functionId: 1,
  visible: true,
  collapsed: false,
  color: null,
  posX: 0,
  posY: 0,
  pinned: false,
  originFunctionId: null,
  originKind: "root",
  originImplied: false,
};

const config: AppConfigDto = {
  tableRowCap: 16,
  callerSuppressThreshold: 32,
  utilityFanInThreshold: 50,
  fanOutAllHardCap: 50,
  nodeCountSoftWarning: 150,
  cardWidthPx: 440,
  summaryConcurrency: 4,
  layoutHeightChangeThresholdPx: 8,
  layoutAnimationMs: 400,
  summaryDemandDebounceMs: 250,
  publicMode: false,
  nodeColorPalette: ["slate"],
  adapters: { ghidra: "mock", llm: "mock", llmModel: "mock-llm-v1" },
};

const mainFn: FunctionDto = {
  id: 1,
  binaryId: 1,
  address: 0x401000,
  displayName: "main",
  nameGhidra: "main",
  nameAnalyst: null,
    nameLlm: null,
  isRenamed: false,
  parameters: [],
  signature: null,
  assembly: "; disassembly of main",
  codeC: "int main(int arg0) { return arg0; }",
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
    adapter: null,
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

function renderWithProviders() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ConfigProvider fallback={<p>loading</p>}>
        <ReactFlowProvider>
          <FunctionCardNode data={{ functionId: 1, viewId: 1, viewNode }} />
        </ReactFlowProvider>
      </ConfigProvider>
    </QueryClientProvider>,
  );
}

describe("FunctionCardNode", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = input instanceof Request ? input.url : String(input);
        if (url.endsWith("/api/v1/config")) {
          return Promise.resolve(new Response(JSON.stringify(config), { status: 200 }));
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
        if (url.endsWith("/api/v1/functions/1/summary/regenerate")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({ functionId: 1, summaryStatus: "pending", queuePosition: 0, summaryShort: null }),
              { status: 202 },
            ),
          );
        }
        return Promise.reject(new Error(`Unexpected fetch: ${url}`));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the card header, summary, and both neighbour tables once loaded", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("main")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Callees")).toBeInTheDocument();
    });
    expect(screen.getByText("Callers")).toBeInTheDocument();
  });

  it("refreshes the function summary on request", async () => {
    renderWithProviders();

    fireEvent.click(await screen.findByRole("button", { name: /refresh summary for main/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/functions/1/summary/regenerate",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });
});
