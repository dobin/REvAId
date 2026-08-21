import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { UtilityGroup } from "./UtilityGroup";
import type { NeighbourPageDto } from "@/api/types";

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
      <UtilityGroup functionId={1} viewId={1} direction="callees" totalUtility={7} />
    </QueryClientProvider>,
  );
}

describe("UtilityGroup", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(utilityPage), { status: 200 }))),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders collapsed by default with the count, and does not fetch", () => {
    renderWithProviders();
    expect(screen.getByText(/utility calls \(7\)/i)).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("fetches and renders utility rows once expanded", async () => {
    renderWithProviders();
    fireEvent.click(screen.getByRole("button", { name: /utility calls/i }));

    await waitFor(() => {
      expect(screen.getByText("memcpy_helper")).toBeInTheDocument();
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when totalUtility is zero", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <UtilityGroup functionId={1} viewId={1} direction="callees" totalUtility={0} />
      </QueryClientProvider>,
    );
    expect(screen.queryByText(/utility calls/i)).not.toBeInTheDocument();
  });
});
