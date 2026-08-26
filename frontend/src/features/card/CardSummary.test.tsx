import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CardSummary } from "./CardSummary";
import type { FunctionDto } from "@/api/types";

function renderWithClient(node: React.ReactElement) {
  const queryClient = new QueryClient();
  return render(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>);
}

const baseFn: FunctionDto = {
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
  callerCount: 0,
  hasIndirectCalls: false,
};

describe("CardSummary", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders nothing when no summary exists yet", () => {
    const { container } = renderWithClient(<CardSummary fn={baseFn} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the short summary when ready", () => {
    renderWithClient(
      <CardSummary
        fn={{ ...baseFn, summary: { ...baseFn.summary, status: "ready", short: "Entry point." } }}
      />,
    );
    expect(screen.getByText(/entry point/i)).toBeInTheDocument();
  });

  it("renders a shimmering generating message when pending", () => {
    renderWithClient(
      <CardSummary fn={{ ...baseFn, summary: { ...baseFn.summary, status: "pending" } }} />,
    );
    const shimmer = screen.getByText(/generating/i);
    expect(shimmer).toBeInTheDocument();
    expect(shimmer).toHaveClass("gr-shimmer");
  });

  it("renders a retry button on error and regenerates on click", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({ functionId: 1, summaryStatus: "pending", queuePosition: 0, summaryShort: null }),
            { status: 202 },
          ),
        ),
      ),
    );
    renderWithClient(
      <CardSummary
        fn={{
          ...baseFn,
          summary: { ...baseFn.summary, status: "error", errorCode: "SUMMARY_PROVIDER_ERROR" },
        }}
      />,
    );
    const retryButton = screen.getByRole("button", { name: /retry summary/i });
    fireEvent.click(retryButton);
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });
  });
});
