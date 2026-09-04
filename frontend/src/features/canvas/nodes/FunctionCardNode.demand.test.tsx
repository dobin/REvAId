/**
 * Placing a card requests its own summary and the bounded visible windows of
 * its caller/callee tables.
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
  cardWidthPx: 440,
  summaryConcurrency: 4,
  layoutHeightChangeThresholdPx: 8,
  layoutAnimationMs: 400,
  summaryDemandDebounceMs: 10,
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

describe("FunctionCardNode summary demand", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("demands the placed card and its visible caller/callee rows", async () => {
    mockFetch();
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("main", { selector: "*" })).toBeInTheDocument();
    });

    await waitFor(
      () => {
        expect(demandCallCount()).toBeGreaterThan(1);
      },
      { timeout: 2000 },
    );

    // The virtualizer determines how many rows are mounted (jsdom's viewport
    // is smaller than a browser's), but demand must remain bounded to the
    // card plus the two initial table windows.
    expect(demandCallCount()).toBeLessThanOrEqual(20);

    const summaryUrls = vi.mocked(global.fetch).mock.calls
      .map(([input]) => (input instanceof Request ? input.url : String(input)))
      .filter((url) => url.includes("/summary"));
    expect(summaryUrls).toEqual(
      expect.arrayContaining([
        expect.stringContaining("/functions/1/summary"),
        expect.stringContaining("/functions/1000/summary"),
        expect.stringContaining("/functions/1013/summary"),
      ]),
    );
  });
});
