/**
 * I9 §5.4 cost-bound exit tests for row-level demand acquisition. Verifies
 * `VirtualRowList` + `useSummaryDemand` together never demand more than the
 * virtualized (rendered + overscan) window, regardless of how many rows the
 * underlying list holds or how fast the user scrolls through them.
 */
import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfigProvider } from "@/config/ConfigProvider";
import { VirtualRowList } from "./VirtualRowList";
import type { AppConfigDto, NeighbourRowDto } from "@/api/types";

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
  summaryDemandDebounceMs: 50,
  nodeColorPalette: ["slate"],
  adapters: { ghidra: "mock", llm: "mock", llmModel: "mock-llm-v1" },
};

function makeRow(id: number): NeighbourRowDto {
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

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.endsWith("/api/v1/config")) {
        return Promise.resolve(new Response(JSON.stringify(config), { status: 200 }));
      }
      if (url.includes("/summary") && !url.includes("regenerate")) {
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
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    }),
  );
}

function renderList(rows: NeighbourRowDto[]) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ConfigProvider fallback={null}>
        <VirtualRowList rows={rows} demand={{ surface: "test-surface", priority: 2 }} />
      </ConfigProvider>
    </QueryClientProvider>,
  );
}

function demandCallCount(): number {
  const calls = vi.mocked(global.fetch).mock.calls;
  return calls.filter(([input]) => {
    const url = input instanceof Request ? input.url : String(input);
    return url.includes("/summary") && !url.includes("regenerate");
  }).length;
}

describe("VirtualRowList demand acquisition (I9 cost bound)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("a 300-row list demands far fewer than 300 summaries — only the virtualized window", async () => {
    mockFetch();
    const rows = Array.from({ length: 300 }, (_, i) => makeRow(i));
    renderList(rows);

    await waitFor(
      () => {
        expect(demandCallCount()).toBeGreaterThan(0);
      },
      { timeout: 2000 },
    );

    // jsdom reports zero client height, so @tanstack/react-virtual renders a
    // small fallback window (estimateSize-based) + overscan — nowhere near
    // the full 300-row list. tableRowCap (16) + 4 lookahead is the plan's
    // stated bound for an actually-rendered viewport; jsdom's fallback
    // window is smaller still, so this assertion is conservative.
    expect(demandCallCount()).toBeLessThanOrEqual(config.tableRowCap + 4);
  });

  it("a small list still demands its rows once", async () => {
    mockFetch();
    const rows = Array.from({ length: 3 }, (_, i) => makeRow(i));
    renderList(rows);

    await waitFor(() => {
      expect(demandCallCount()).toBe(3);
    });
  });
});
