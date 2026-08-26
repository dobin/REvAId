/**
 * I9 §5.4: "placing one typical card demands <= 20 summaries (median)."
 * `FunctionCardNode` demands its own summary (priority 0) plus whatever its
 * two `NeighbourTable`s' `VirtualRowList`s acquire — capped at
 * `tableRowCap` rows per direction by the backend page size, so a typical
 * card (16 callees + a few callers) stays comfortably under 20.
 *
 * Note: React Flow marks its node subtree `aria-hidden`, so role queries
 * inside a `FunctionCardNode` need `{ hidden: true }` — see
 * `/memories/repo/graphrev.md`.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactFlowProvider } from "@xyflow/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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
  cardWidthPx: 380,
  summaryConcurrency: 4,
  layoutHeightChangeThresholdPx: 8,
  layoutAnimationMs: 400,
  summaryDemandDebounceMs: 10,
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
  callerCount: 3,
  hasIndirectCalls: false,
};

function makeRow(id: number): NeighbourPageDto["rows"][number] {
  return {
    id,
    address: 0x1000 + id,
    displayName: `fn_${String(id)}`,
    isRenamed: false,
      nameLlm: null,
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
  };
}

function page(direction: "callees" | "callers", count: number): NeighbourPageDto {
  return {
    functionId: 1,
    direction,
    group: "primary",
    rows: Array.from({ length: count }, (_, i) => makeRow(1000 + i)),
    total: count,
    totalPrimary: count,
    totalUtility: 0,
    limit: 16,
    offset: 0,
    callersSuppressed: false,
    mayBeIncomplete: false,
  };
}

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.endsWith("/api/v1/config")) {
        return Promise.resolve(new Response(JSON.stringify(config), { status: 200 }));
      }
      if (url.includes("/api/v1/functions/1/neighbours")) {
        const direction = url.includes("direction=callers") ? "callers" : "callees";
        const count = direction === "callees" ? 16 : 3;
        return Promise.resolve(new Response(JSON.stringify(page(direction, count)), { status: 200 }));
      }
      if (url.endsWith("/api/v1/functions/1")) {
        return Promise.resolve(new Response(JSON.stringify(mainFn), { status: 200 }));
      }
      if (url.includes("/summary")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              functionId: 1,
              summaryStatus: "pending",
              queuePosition: 0,
              summaryShort: null,
            }),
            { status: 202 },
          ),
        );
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    }),
  );
}

function demandCallCount(): number {
  return vi.mocked(global.fetch).mock.calls.filter(([input]) => {
    const url = input instanceof Request ? input.url : String(input);
    return url.includes("/summary");
  }).length;
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

describe("FunctionCardNode demand acquisition (I9 cost bound)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("placing one card (16 callees + 3 callers) demands <= 20 summaries", async () => {
    mockFetch();
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("main", { selector: "*" })).toBeInTheDocument();
    });

    await waitFor(
      () => {
        // own summary (1) + up to 16 callee rows + up to 3 caller rows.
        expect(demandCallCount()).toBeGreaterThan(0);
      },
      { timeout: 2000 },
    );

    expect(demandCallCount()).toBeLessThanOrEqual(20);
  });
});
