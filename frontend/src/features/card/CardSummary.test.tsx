import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    const summary = screen.getByRole("button", { name: /show full summary on hover/i });
    expect(summary).toHaveTextContent(/entry point/i);
    expect(summary).toHaveStyle({ fontSize: "0.9375rem", color: "rgb(0, 0, 0)" });
  });

  it("opens a tooltip with the full long summary on hover", async () => {
    const user = userEvent.setup();
    renderWithClient(
      <CardSummary
        fn={{
          ...baseFn,
          summary: {
            ...baseFn.summary,
            status: "ready",
            short: "Entry point.",
            long: "Sets up the runtime then dispatches to the real main.",
          },
        }}
      />,
    );
    // The long text is not shown inline (the card only clamps the short line).
    expect(
      screen.queryByText(/sets up the runtime then dispatches/i),
    ).not.toBeInTheDocument();

    await user.hover(screen.getByRole("button", { name: /show full summary on hover/i }));

    expect(
      await screen.findByText(/sets up the runtime then dispatches/i),
    ).toBeInTheDocument();
  });

  it("does not bubble a click on the hover trigger (card stays unselected)", async () => {
    const user = userEvent.setup();
    const onParentClick = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        {/* Mirrors FunctionCardNode's click-to-select wrapper around the summary. */}
        <div onClick={onParentClick}>
          <CardSummary
            fn={{
              ...baseFn,
              summary: { ...baseFn.summary, status: "ready", short: "Entry point.", long: "More." },
            }}
          />
        </div>
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("button", { name: /show full summary on hover/i }));
    expect(onParentClick).not.toHaveBeenCalled();
  });

  it("renders a generating message with a spinner when pending", () => {
    renderWithClient(
      <CardSummary fn={{ ...baseFn, summary: { ...baseFn.summary, status: "pending" } }} />,
    );
    const message = screen.getByText(/generating/i);
    expect(message).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /summary generating/i })).toBeInTheDocument();
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
