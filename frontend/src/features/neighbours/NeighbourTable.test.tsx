import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfigProvider } from "@/config/ConfigProvider";
import { NeighbourTable } from "./NeighbourTable";
import type { AppConfigDto, NeighbourPageDto, NeighbourRowDto } from "@/api/types";

// I9: VirtualRowList/UtilityGroup now call useSummaryDemand, which needs a
// resolved ConfigProvider (for summaryDemandDebounceMs) even in tests that
// only render one card's tables in isolation.
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
  nodeColorPalette: ["slate"],
  adapters: { ghidra: "mock", llm: "mock", llmModel: "mock-llm-v1" },
};

function makeRow(id: number, overrides: Partial<NeighbourRowDto> = {}): NeighbourRowDto {
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
    ...overrides,
  };
}

function renderWithProviders(
  functionId: number,
  viewId: number,
  direction: "callees" | "callers",
) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ConfigProvider fallback={null}>
        <NeighbourTable functionId={functionId} viewId={viewId} direction={direction} />
      </ConfigProvider>
    </QueryClientProvider>,
  );
}

function mockFetchOnce(page: NeighbourPageDto) {
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

describe("NeighbourTable", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders a capped, possibly-incomplete callee page (dispatch_large: 300+ callees)", async () => {
    const page: NeighbourPageDto = {
      functionId: 10,
      direction: "callees",
      group: "primary",
      rows: Array.from({ length: 16 }, (_, i) => makeRow(i)),
      total: 312,
      totalPrimary: 312,
      totalUtility: 0,
      limit: 16,
      offset: 0,
      callersSuppressed: false,
      mayBeIncomplete: true,
    };
    mockFetchOnce(page);
    renderWithProviders(10, 1, "callees");

    await waitFor(() => {
      expect(screen.getByText("fn_0")).toBeInTheDocument();
    });
    expect(screen.getByText(/may be incomplete/i)).toBeInTheDocument();
  });

  it("renders only SuppressedNotice for a suppressed caller page (mem_copy_block: 291 callers)", async () => {
    const page: NeighbourPageDto = {
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
    mockFetchOnce(page);
    renderWithProviders(20, 1, "callers");

    await waitFor(() => {
      expect(screen.getByText(/called by 291/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /sort callers direction/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/filter callers/i)).not.toBeInTheDocument();
  });

  it("renders a normal, non-suppressed page with filter and sort controls", async () => {
    const page: NeighbourPageDto = {
      functionId: 1,
      direction: "callees",
      group: "primary",
      rows: [makeRow(1, { displayName: "entry_child_00" })],
      total: 16,
      totalPrimary: 16,
      totalUtility: 0,
      limit: 16,
      offset: 0,
      callersSuppressed: false,
      mayBeIncomplete: false,
    };
    mockFetchOnce(page);
    renderWithProviders(1, 1, "callees");

    await waitFor(() => {
      expect(screen.getByText("entry_child_00")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Filter callees")).toBeInTheDocument();
    expect(screen.getByLabelText("Sort callees")).toBeInTheDocument();
  });
});
