import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NeighbourTable } from "./NeighbourTable";
import type { NeighbourPageDto, NeighbourRowDto } from "@/api/types";

function makeRow(id: number, overrides: Partial<NeighbourRowDto> = {}): NeighbourRowDto {
  return {
    id,
    address: 0x1000 + id,
    displayName: `fn_${String(id)}`,
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

function renderWithProviders(
  functionId: number,
  viewId: number,
  direction: "callees" | "callers",
) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <NeighbourTable functionId={functionId} viewId={viewId} direction={direction} />
    </QueryClientProvider>,
  );
}

function mockFetchOnce(page: NeighbourPageDto) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(page), { status: 200 }))),
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
      expect(screen.getByText("showing 16 of 312")).toBeInTheDocument();
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
