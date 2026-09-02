/**
 * ADR 0006: the view picker lists only this browser's owned views in
 * public mode and skips the shared `last-view` write; private mode keeps
 * the full listing + B16 persistence.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/api/client";
import type { ViewDto, ViewSummaryDto } from "@/api/types";
import { getLatestMyViewId, getMyViews, recordMyView } from "@/lib/myViews";
import { ViewPicker } from "./ViewPicker";

const configMock = vi.hoisted(() => ({ publicMode: false }));
vi.mock("@/config/ConfigProvider", () => ({
  useConfig: () => configMock,
}));

const views: ViewSummaryDto[] = [
  {
    id: 5,
    binaryId: 1,
    name: "Default",
    rootFunctionId: null,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
  },
  {
    id: 6,
    binaryId: 1,
    name: "Someone else's view",
    rootFunctionId: null,
    createdAt: "2026-01-02T00:00:00Z",
    updatedAt: "2026-01-02T00:00:00Z",
  },
];

const createdView: ViewDto = {
  id: 42,
  binaryId: 1,
  name: "My view",
  rootFunctionId: null,
  camera: { x: 0, y: 0, zoom: 1 },
  nodes: [],
  createdAt: "2026-01-03T00:00:00Z",
  updatedAt: "2026-01-03T00:00:00Z",
};

function renderPicker() {
  const queryClient = new QueryClient();
  queryClient.setQueryData(["views", 1], views);
  render(
    <QueryClientProvider client={queryClient}>
      <ViewPicker binaryId={1} value={null} onChange={() => undefined} />
    </QueryClientProvider>,
  );
  return queryClient;
}

describe("ViewPicker (public mode)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    configMock.publicMode = false;
  });
  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("private mode: lists all views and persists the switch via last-view", async () => {
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue(undefined);
    renderPicker();

    const select = screen.getByLabelText<HTMLSelectElement>("View");
    expect(select.options).toHaveLength(3); // placeholder + 2 views
    expect(screen.getByText("Someone else's view")).toBeInTheDocument();

    fireEvent.change(select, { target: { value: "6" } });
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/binaries/1/last-view", { viewId: 6 });
    });
  });

  it("public mode: lists only this browser's owned views, no listing fetch", () => {
    configMock.publicMode = true;
    recordMyView(1, 5, "Default");
    const getSpy = vi.spyOn(apiClient, "get");
    renderPicker();

    const select = screen.getByLabelText<HTMLSelectElement>("View");
    // placeholder + only the owned view (5); view 6 stays invisible.
    expect(select.options).toHaveLength(2);
    expect(screen.queryByText("Someone else's view")).not.toBeInTheDocument();
    // No listing request in public mode — owned views come from localStorage.
    expect(getSpy).not.toHaveBeenCalled();
  });

  it("public mode: switching views records ownership and skips last-view", async () => {
    configMock.publicMode = true;
    recordMyView(1, 5, "Default");
    recordMyView(1, 6, "Second");
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue(undefined);
    renderPicker();

    const select = screen.getByLabelText<HTMLSelectElement>("View");
    fireEvent.change(select, { target: { value: "6" } });

    await waitFor(() => {
      // No last-view write in public mode — the pointer is browser-local.
      expect(postSpy).not.toHaveBeenCalledWith("/binaries/1/last-view", { viewId: 6 });
    });
    // Ownership reordered: 6 is now the latest owned view.
    expect(getLatestMyViewId(1)).toBe(6);
  });

  it("public mode: creating a view records it as owned", async () => {
    configMock.publicMode = true;
    recordMyView(1, 5, "Default");
    const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("My view");
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue(createdView);
    renderPicker();

    fireEvent.click(screen.getByLabelText("New view"));
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/binaries/1/views", { name: "My view" });
    });
    expect(getMyViews(1)).toContainEqual({ id: 42, name: "My view" });
    expect(promptSpy).toHaveBeenCalled();
  });
});
