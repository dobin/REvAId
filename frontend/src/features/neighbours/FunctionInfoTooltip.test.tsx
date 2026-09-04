import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FunctionInfoTooltip } from "./FunctionInfoTooltip";
import type { FunctionDto } from "@/api/types";

function makeFunction(overrides: Partial<FunctionDto["summary"]> = {}): FunctionDto {
  return {
    id: 7,
    binaryId: 1,
    address: 0x401000,
    displayName: "parse_header",
    nameGhidra: "FUN_00401000",
    nameAnalyst: "parse_header",
    nameLlm: null,
    isRenamed: true,
    parameters: [],
    signature: null,
    assembly: null,
    codeC: null,
    kind: "normal",
    placeholderModule: null,
    fanIn: 2,
    fanOut: 3,
    isUtility: false,
    utilitySource: "computed",
    utilityOverride: null,
    summary: {
      status: "ready",
      short: "Parses the file header.",
      long: "Reads the first bytes and validates the magic number before dispatching.",
      model: "mock",
      adapter: null,
      errorCode: null,
      lowConfidence: false,
      generatedAt: "2026-01-01T00:00:00Z",
      isStale: false,
      ...overrides,
    },
    notes: "",
    hasNotes: false,
    notesUpdatedAt: null,
    calleeCount: 3,
    callerCount: 2,
    hasIndirectCalls: false,
  };
}

function renderTooltip(fn: FunctionDto) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(fn), { status: 200 }))),
  );
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <FunctionInfoTooltip functionId={fn.id}>
        <span>{fn.displayName}</span>
      </FunctionInfoTooltip>
    </QueryClientProvider>,
  );
}

// The component opens the popup after a short real-timer delay; `findBy*`
// queries below poll until it appears, so no manual timer plumbing is needed.
function hover() {
  fireEvent.mouseEnter(screen.getByText("parse_header").parentElement as HTMLElement);
}

describe("FunctionInfoTooltip", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not fetch or show the popup before hover", () => {
    renderTooltip(makeFunction());
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("shows short and long summary on hover", async () => {
    renderTooltip(makeFunction());
    hover();

    expect(await screen.findByText("Parses the file header.")).toBeInTheDocument();
    expect(
      screen.getByText(/Reads the first bytes and validates the magic number/),
    ).toBeInTheDocument();
  });

  it("hides the popup again on unhover", async () => {
    renderTooltip(makeFunction());
    const wrapper = screen.getByText("parse_header").parentElement as HTMLElement;
    hover();
    await screen.findByRole("tooltip");

    fireEvent.mouseLeave(wrapper);
    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
  });

  it("stays open when the pointer moves from the anchor onto the popup", async () => {
    renderTooltip(makeFunction());
    const wrapper = screen.getByText("parse_header").parentElement as HTMLElement;
    hover();
    const tooltip = await screen.findByRole("tooltip");
    // Wait out the async fetch so the body (and its long text) is settled
    // before we probe the hover bridge — avoids an act() warning too.
    await screen.findByText(/Reads the first bytes and validates the magic number/);

    // Pointer leaves the anchor (schedules a delayed close) but immediately
    // enters the popup (must cancel that close) — the popup must survive.
    fireEvent.mouseLeave(wrapper);
    fireEvent.mouseEnter(tooltip);

    // Give the close delay time to (not) fire, then confirm it's still there
    // and its long, scrollable text is reachable.
    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    expect(
      screen.getByText(/Reads the first bytes and validates the magic number/),
    ).toBeInTheDocument();
  });

  it("closes when the pointer finally leaves the popup", async () => {
    renderTooltip(makeFunction());
    const wrapper = screen.getByText("parse_header").parentElement as HTMLElement;
    hover();
    const tooltip = await screen.findByRole("tooltip");

    fireEvent.mouseLeave(wrapper);
    fireEvent.mouseEnter(tooltip);
    fireEvent.mouseLeave(tooltip);

    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
  });

  it("falls back to a placeholder when there is no summary", async () => {
    renderTooltip(makeFunction({ status: "none", short: null, long: null }));
    hover();
    expect(await screen.findByText("No summary yet.")).toBeInTheDocument();
  });
});
