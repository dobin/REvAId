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
  nameGhidra: "main",
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
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(functionDto), { status: 200 }))),
    );

    render(
      <QueryClientProvider client={new QueryClient()}>
        <DetailPanel />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText((_, element) => element?.tagName === "CODE" && element.textContent === functionDto.codeC),
    ).toBeInTheDocument();
    expect(
      screen.getByText((_, element) => element?.tagName === "CODE" && element.textContent === functionDto.assembly),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Function detail")).toHaveStyle({ width: "42rem" });
  });

  it("explains when the function has no decompilation or assembly", async () => {
    act(() => {
      useAppStore.getState().selectFunction(1);
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ ...functionDto, codeC: null, assembly: null }), { status: 200 }),
        ),
      ),
    );

    render(
      <QueryClientProvider client={new QueryClient()}>
        <DetailPanel />
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
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(functionDto), { status: 200 }))),
    );

    render(
      <QueryClientProvider client={new QueryClient()}>
        <DetailPanel />
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /close function detail/i }));
    expect(screen.queryByLabelText(/function detail/i)).not.toBeInTheDocument();
  });
});
