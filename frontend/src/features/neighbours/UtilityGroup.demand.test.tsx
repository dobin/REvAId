/**
 * Utility rows acquire demand while expanded and release it when collapsed.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfigProvider } from "@/config/ConfigProvider";
import { UtilityGroup } from "./UtilityGroup";
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
  nodeColorPalette: ["slate"],
  adapters: { ghidra: "mock", llm: "mock", llmModel: "mock-llm-v1" },
};

const utilityPage: NeighbourPageDto = {
  functionId: 1,
  direction: "callees",
  group: "utility",
  rows: Array.from({ length: 7 }, (_, i) => ({
    id: 100 + i,
    address: 0x2000 + i,
    displayName: `utility_${String(i)}`,
    isRenamed: false,
    nameLlm: null,
    summaryShort: null,
    summaryStatus: "none" as const,
    summaryLowConfidence: false,
    kind: "normal" as const,
    onCanvas: false,
    isUtility: true,
    utilitySource: "computed" as const,
    fanIn: 291,
    isSelf: false,
    hasNotes: false,
  })),
  total: 7,
  totalPrimary: 16,
  totalUtility: 7,
  limit: 16,
  offset: 0,
  callersSuppressed: false,
  mayBeIncomplete: false,
};

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.endsWith("/api/v1/config")) {
        return Promise.resolve(new Response(JSON.stringify(config), { status: 200 }));
      }
      if (url.includes("/neighbours")) {
        return Promise.resolve(new Response(JSON.stringify(utilityPage), { status: 200 }));
      }
      if (url.includes("/summary") && init?.method !== "DELETE") {
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
      return Promise.resolve(new Response(null, { status: 204 }));
    }),
  );
}

function demandCallCount(): number {
  return vi.mocked(global.fetch).mock.calls.filter(([input, init]) => {
    const url = input instanceof Request ? input.url : String(input);
    return url.includes("/summary") && init?.method !== "DELETE";
  }).length;
}

function releaseCallCount(): number {
  return vi.mocked(global.fetch).mock.calls.filter(([input, init]) => {
    const url = input instanceof Request ? input.url : String(input);
    return url.includes("/summary") && init?.method === "DELETE";
  }).length;
}

describe("UtilityGroup demand acquisition", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("expanding demands its rows and collapsing releases them", async () => {
    mockFetch();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <ConfigProvider fallback={null}>
          <UtilityGroup functionId={1} viewId={1} direction="callees" totalUtility={7} priority={1} />
        </ConfigProvider>
      </QueryClientProvider>,
    );

    expect(demandCallCount()).toBe(0);

    const expandButton = await screen.findByRole("button", { name: /utility calls/i });
    fireEvent.click(expandButton);

    await waitFor(() => expect(demandCallCount()).toBe(7));

    fireEvent.click(expandButton);

    await waitFor(() => expect(releaseCallCount()).toBe(7));
  });
});
