import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DetailPanel } from "./DetailPanel";
import { useAppStore } from "@/store";
import type { FunctionDto } from "@/api/types";

const functionDto: FunctionDto = {
  id: 1,
  binaryId: 1,
  address: 0x401000,
  displayName: "main",
  name: "main",
  nameAnalyst: null,
  nameLlm: null,
  isRenamed: false,
  parameters: [],
  signature: "int main(void)",
  assembly: "PUSH RBP\nRET",
  codeC: "int main(void) {\n  return 0;\n}",
  kind: "normal",
  placeholderModule: null,
  fanIn: 0,
  fanOut: 0,
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
  calleeCount: 0,
  callerCount: 0,
  hasIndirectCalls: false,
};

function neighbourPage(
  direction: "callers" | "callees",
  displayName: string,
  group: "primary" | "utility" = "primary",
) {
  return {
    functionId: 1,
    direction,
    group,
    rows: displayName ? [{
      id: direction === "callers" ? 2 : 3,
      address: 0x401100,
      displayName,
      nameLlm: null,
      isRenamed: false,
      summaryShort: null,
      summaryStatus: "none",
      summaryLowConfidence: false,
      kind: "normal",
      onCanvas: false,
      isUtility: false,
      utilitySource: "computed",
      fanIn: 0,
      isSelf: false,
      hasNotes: false,
      canFanOut: true,
    }] : [],
    total: displayName ? 1 : 0,
    totalPrimary: group === "primary" ? 1 : 0,
    totalUtility: group === "utility" ? 1 : 0,
    limit: 500,
    offset: 0,
    callersSuppressed: false,
    mayBeIncomplete: false,
  };
}

function mockWorkspaceFetch() {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/neighbours?")) {
      const direction = url.includes("direction=callers") ? "callers" : "callees";
      const group = url.includes("group=utility") ? "utility" : "primary";
      return Promise.resolve(new Response(JSON.stringify(neighbourPage(
        direction,
        group === "primary" ? (direction === "callers" ? "caller_fn" : "callee_fn") : "",
        group,
      )), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify(functionDto), { status: 200 }));
  }));
}

describe("DetailPanel", () => {
  afterEach(() => {
    act(() => {
      useAppStore.getState().clearSelection();
    });
    vi.unstubAllGlobals();
  });

  it("shows readable C source and assembly for the selected function", async () => {
    act(() => {
      useAppStore.getState().selectFunction(1);
    });
    mockWorkspaceFetch();

    render(
      <QueryClientProvider client={new QueryClient()}>
        <DetailPanel viewId={1} />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText((_, element) => element?.tagName === "CODE" && element.textContent === functionDto.codeC),
    ).toBeInTheDocument();
    expect(
      screen.getByText((_, element) => element?.tagName === "CODE" && element.textContent === functionDto.assembly),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Function detail")).toHaveStyle({ width: "42rem" });
    expect(await screen.findByText("caller_fn")).toBeInTheDocument();
    expect(await screen.findByText("callee_fn")).toBeInTheDocument();
  });

  it("explains when the function has no decompilation or assembly", async () => {
    act(() => {
      useAppStore.getState().selectFunction(1);
    });
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/neighbours?")) {
        const direction = url.includes("direction=callers") ? "callers" : "callees";
        const group = url.includes("group=utility") ? "utility" : "primary";
        return Promise.resolve(new Response(JSON.stringify(neighbourPage(direction, "", group)), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ ...functionDto, codeC: null, assembly: null }), { status: 200 }));
    }));

    render(
      <QueryClientProvider client={new QueryClient()}>
        <DetailPanel viewId={1} />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText(/decompilation unavailable/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/assembly unavailable/i)).toBeInTheDocument();
  });

  it("closes when the close button is clicked", async () => {
    act(() => {
      useAppStore.getState().selectFunction(1);
    });
    mockWorkspaceFetch();

    render(
      <QueryClientProvider client={new QueryClient()}>
        <DetailPanel viewId={1} />
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /close function detail/i }));
    expect(screen.queryByLabelText(/function detail/i)).not.toBeInTheDocument();
  });
});
