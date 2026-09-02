import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfigProvider } from "@/config/ConfigProvider";
import { UtilityGroup } from "./UtilityGroup";
import type { AppConfigDto, NeighbourPageDto } from "@/api/types";

// I9: an EXPANDED group's rows call useSummaryDemand, which needs a resolved
// ConfigProvider. The collapsed-by-default test intentionally renders
// WITHOUT ConfigProvider (and asserts zero fetches) since collapsed rows
// never mount at all (C2b) — nothing in that path should need config.
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

const utilityPage: NeighbourPageDto = {
  functionId: 1,
  direction: "callees",
  group: "utility",
  rows: [
    {
      id: 99,
      address: 0x2000,
      displayName: "memcpy_helper",
      isRenamed: false,
    nameLlm: null,
      summaryShort: null,
      summaryStatus: "none",
      summaryLowConfidence: false,
      kind: "normal",
      onCanvas: false,
      isUtility: true,
      utilitySource: "computed",
      fanIn: 291,
      isSelf: false,
      hasNotes: false,
    },
  ],
  total: 7,
  totalPrimary: 16,
  totalUtility: 7,
  limit: 16,
  offset: 0,
  callersSuppressed: false,
  mayBeIncomplete: false,
};

function renderWithProviders() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <UtilityGroup functionId={1} viewId={1} direction="callees" totalUtility={7} priority={1} />
    </QueryClientProvider>,
  );
}

function renderExpandableWithProviders() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ConfigProvider fallback={null}>
        <UtilityGroup functionId={1} viewId={1} direction="callees" totalUtility={7} priority={1} />
      </ConfigProvider>
    </QueryClientProvider>,
  );
}

function mockFetch(page: NeighbourPageDto) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.endsWith("/api/v1/config")) {
        return Promise.resolve(new Response(JSON.stringify(config), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(page), { status: 200 }));
    }),
  );
}

describe("UtilityGroup", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders collapsed by default with the count, and does not fetch", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(utilityPage), { status: 200 }))),
    );
    renderWithProviders();
    expect(screen.getByText(/utility calls \(7\)/i)).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("fetches and renders utility rows once expanded", async () => {
    mockFetch(utilityPage);
    renderExpandableWithProviders();
    const expandButton = await screen.findByRole("button", { name: /utility calls/i });
    fireEvent.click(expandButton);

    await waitFor(() => {
      expect(screen.getByText("memcpy_helper")).toBeInTheDocument();
    });
    const calledUrls = vi.mocked(global.fetch).mock.calls.map((call) => String(call[0]));
    expect(calledUrls.some((url) => url.includes("group=utility"))).toBe(true);
  });

  it("renders nothing when totalUtility is zero", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <UtilityGroup functionId={1} viewId={1} direction="callees" totalUtility={0} priority={1} />
      </QueryClientProvider>,
    );
    expect(screen.queryByText(/utility calls/i)).not.toBeInTheDocument();
  });
});
