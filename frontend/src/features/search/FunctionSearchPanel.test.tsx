import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/api/client";
import type { FunctionSearchPageDto } from "@/api/types";
import { FunctionSearchPanel } from "./FunctionSearchPanel";
import { useAppStore } from "@/store";

const results: FunctionSearchPageDto = {
  rows: [{
    id: 9,
    address: 0x401000,
    displayName: "interesting_fn",
    isRenamed: false,
    kind: "normal",
    isUtility: false,
    fanIn: 1,
    hasNotes: false,
    isEntryPoint: false,
    codeMatches: [
      { lineNumber: 4, text: "    if (needle) {" },
      { lineNumber: 19, text: "    return needle;" },
    ],
    codeMatchesTruncated: true,
  }],
  total: 1,
  limit: 50,
  offset: 0,
  query: "needle",
};

describe("FunctionSearchPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useAppStore.getState().clearSelection();
  });

  it("collapses source lines and adds a function from anywhere on its result row", async () => {
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url === "/views/4") return Promise.resolve({ nodes: [] });
      if (url.includes("/functions?")) return Promise.resolve(results);
      if (url.includes("/neighbours")) {
        return Promise.resolve({ rows: [], total: 0, limit: 10, offset: 0, functionId: 9, direction: "callers", group: "primary", totalPrimary: 0, totalUtility: 0, callersSuppressed: false, mayBeIncomplete: false });
      }
      return Promise.resolve({ rows: [] });
    });
    const patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue({ nodes: [] });
    render(<QueryClientProvider client={new QueryClient()}>
      <FunctionSearchPanel binaryId={1} viewId={4} analysisImageBase={null} runtimeBase={null} />
    </QueryClientProvider>);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search functions" }), { target: { value: "needle" } });
    expect(await screen.findByText(/2\+ matching lines/)).toBeInTheDocument();
    expect(screen.queryByText(/if \(needle\)/)).not.toBeVisible();
    fireEvent.click(screen.getByText(/2\+ matching lines/));
    expect(screen.getByText(/if \(needle\)/)).toBeVisible();
    expect(screen.getByText("if (needle) {")).toBeInTheDocument();
    expect(screen.getByText("return needle;")).toBeInTheDocument();
    expect(screen.getByText("More matching lines not shown (20-line limit).")).toBeInTheDocument();
    expect(screen.queryByText("Canvas", { selector: "th" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add interesting_fn to canvas" }));
    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalled();
    });
    expect(screen.getByRole("searchbox", { name: "Search functions" })).toHaveValue("needle");
    expect(screen.getByText("if (needle) {")).toBeInTheDocument();
  });

  it("opens an existing canvas function when its action button is clicked", async () => {
    const onOpenExisting = vi.fn();
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url === "/views/4") return Promise.resolve({ nodes: [{ functionId: 9, visible: true }] });
      if (url.includes("/functions?")) return Promise.resolve(results);
      return Promise.resolve({ rows: [] });
    });
    const patchSpy = vi.spyOn(apiClient, "patch");
    render(<QueryClientProvider client={new QueryClient()}>
      <FunctionSearchPanel
        binaryId={1}
        viewId={4}
        analysisImageBase={null}
        runtimeBase={null}
        onOpenExisting={onOpenExisting}
      />
    </QueryClientProvider>);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search functions" }), { target: { value: "needle" } });
    fireEvent.click(await screen.findByRole("button", { name: "Open interesting_fn" }));

    expect(onOpenExisting).toHaveBeenCalledWith(9);
    expect(patchSpy).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Open interesting_fn" })).toHaveTextContent("Open");
    expect(screen.getByRole("button", { name: "Open interesting_fn" })).toHaveAttribute(
      "title",
      "Already on canvas — open in the detail panel",
    );
    expect(useAppStore.getState().selectedFunctionId).toBeNull();
  });

  it("opens an existing function when its result row is clicked", async () => {
    const onOpenExisting = vi.fn();
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url === "/views/4") return Promise.resolve({ nodes: [{ functionId: 9, visible: true }] });
      if (url.includes("/functions?")) return Promise.resolve(results);
      return Promise.resolve({ rows: [] });
    });
    const patchSpy = vi.spyOn(apiClient, "patch");
    render(<QueryClientProvider client={new QueryClient()}>
      <FunctionSearchPanel
        binaryId={1}
        viewId={4}
        analysisImageBase={null}
        runtimeBase={null}
        onOpenExisting={onOpenExisting}
      />
    </QueryClientProvider>);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search functions" }), { target: { value: "needle" } });
    fireEvent.click(await screen.findByRole("row", { name: "Open interesting_fn on canvas" }));

    expect(onOpenExisting).toHaveBeenCalledOnce();
    expect(patchSpy).not.toHaveBeenCalled();
    expect(useAppStore.getState().selectedFunctionId).toBeNull();
  });

  it("keeps Search open and reports a successful add", async () => {
    const onAdded = vi.fn();
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url === "/views/4") return Promise.resolve({ nodes: [] });
      if (url.includes("/functions?")) return Promise.resolve(results);
      if (url.includes("/neighbours")) {
        return Promise.resolve({ rows: [], total: 0, limit: 10, offset: 0, functionId: 9, direction: "callers", group: "primary", totalPrimary: 0, totalUtility: 0, callersSuppressed: false, mayBeIncomplete: false });
      }
      return Promise.resolve({ rows: [] });
    });
    vi.spyOn(apiClient, "patch").mockResolvedValue({ nodes: [] });
    render(<QueryClientProvider client={new QueryClient()}>
      <FunctionSearchPanel
        binaryId={1}
        viewId={4}
        analysisImageBase={null}
        runtimeBase={null}
        focusCanvas={false}
        onAdded={onAdded}
      />
    </QueryClientProvider>);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search functions" }), { target: { value: "needle" } });
    fireEvent.click(await screen.findByRole("button", { name: "Add interesting_fn to canvas" }));

    await waitFor(() => {
      expect(onAdded).toHaveBeenCalledOnce();
    });
    expect(useAppStore.getState().selectedFunctionId).toBe(9);
    expect(screen.getByRole("searchbox", { name: "Search functions" })).toHaveValue("needle");
    expect(screen.getByText("interesting_fn")).toBeInTheDocument();
  });

  it("reveals matching C lines on hover and collapses them on pointer exit", async () => {
    vi.spyOn(apiClient, "get").mockImplementation((url: string) => {
      if (url === "/views/4") return Promise.resolve({ nodes: [] });
      if (url.includes("/functions?")) return Promise.resolve(results);
      return Promise.resolve({ rows: [] });
    });
    render(<QueryClientProvider client={new QueryClient()}>
      <FunctionSearchPanel binaryId={1} viewId={4} analysisImageBase={null} runtimeBase={null} />
    </QueryClientProvider>);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search functions" }), { target: { value: "needle" } });
    const matchSummary = await screen.findByText(/2\+ matching lines/);
    const details = matchSummary.closest("details");
    if (!details) throw new Error("C matches details container was not rendered");
    expect(screen.getByText("if (needle) {")).not.toBeVisible();

    fireEvent.mouseEnter(details);
    expect(screen.getByText("if (needle) {")).toBeVisible();
    fireEvent.mouseLeave(details);
    expect(screen.getByText("if (needle) {")).not.toBeVisible();
  });

});
