/**
 * I9 §5.4: "opening a suppressed hub enqueues only its own summary." A
 * suppressed caller table (D7/E2a) renders `SuppressedNotice` only —
 * `VirtualRowList`/`UtilityGroup` never mount, so `useSummaryDemand` never
 * runs for that table. This test proves zero `/summary` demand calls
 * originate from a suppressed table, even though its function has 291
 * callers.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfigProvider } from "@/config/ConfigProvider";
import { NeighbourTable } from "./NeighbourTable";
import type { AppConfigDto, NeighbourPageDto } from "@/api/types";

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

const suppressedPage: NeighbourPageDto = {
  functionId: 20,
  direction: "callers",
  group: "primary",
  rows: [],
  total: 291,
  totalPrimary: 0,
  totalUtility: 0,
  limit: 16,
  offset: 0,
  callersSuppressed: true,
  mayBeIncomplete: false,
};

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.endsWith("/api/v1/config")) {
        return Promise.resolve(new Response(JSON.stringify(config), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(suppressedPage), { status: 200 }));
    }),
  );
}

describe("NeighbourTable demand acquisition (I9 cost bound)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("a suppressed caller table (291 callers) never demands any row summary", async () => {
    mockFetch();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <ConfigProvider fallback={null}>
          <NeighbourTable functionId={20} viewId={1} direction="callers" />
        </ConfigProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText(/called by 291/i)).toBeInTheDocument();
    });

    const summaryCalls = vi.mocked(global.fetch).mock.calls.filter(([input]) => {
      const url = input instanceof Request ? input.url : String(input);
      return url.includes("/summary");
    });
    expect(summaryCalls).toHaveLength(0);
  });
});
