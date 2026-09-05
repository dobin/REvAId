import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BinariesPage } from "./BinariesPage";
import type { BinarySummaryDto } from "@/api/types";

const binaries: BinarySummaryDto[] = [
  {
    id: 1,
    name: "test.exe",
    version: "1.0",
    analysisImageBase: 0x400000,
    functionCount: 180,
    edgeCount: 400,
    lastViewId: null,
    createdAt: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "libparse.dll",
    version: "2.3",
    analysisImageBase: null,
    functionCount: 60,
    edgeCount: 90,
    lastViewId: 7,
    createdAt: "2026-02-02T00:00:00Z",
  },
];

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

function renderPage(path = "/") {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <BinariesPage />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BinariesPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = input instanceof Request ? input.url : String(input);
        if (url.endsWith("/api/v1/binaries")) {
          return Promise.resolve(new Response(JSON.stringify(binaries), { status: 200 }));
        }
        return Promise.reject(new Error(`Unexpected fetch: ${url}`));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a loading state, then one row per binary with stats", async () => {
    renderPage();
    expect(screen.getByText(/loading binaries/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("test.exe")).toBeInTheDocument();
    });
    expect(screen.getByText("libparse.dll")).toBeInTheDocument();
    expect(screen.getByText("180")).toBeInTheDocument();
    expect(screen.getByText("400")).toBeInTheDocument();
  });

  it("navigates to /{name}/ when Open is clicked", async () => {
    const user = userEvent.setup();
    renderPage();

    const openButtons = await screen.findAllByRole("button", { name: "Open" });
    const firstOpen = openButtons[0];
    if (!firstOpen) throw new Error("No Open button found");
    await user.click(firstOpen);

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/test.exe/");
    });
  });

  it("shows the stats dialog with counts", async () => {
    const user = userEvent.setup();
    renderPage();

    const statsButtons = await screen.findAllByRole("button", { name: "Stats" });
    const secondStats = statsButtons[1];
    if (!secondStats) throw new Error("No Stats button found");
    await user.click(secondStats);

    expect(await screen.findByText(/Stats — libparse\.dll/)).toBeInTheDocument();
    expect(screen.getByText("Call edges")).toBeInTheDocument();
    expect(screen.getByText("#7")).toBeInTheDocument();
  });

  it("deletes a binary via the typed-name confirm dialog", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.endsWith("/api/v1/binaries")) {
        return Promise.resolve(new Response(JSON.stringify(binaries), { status: 200 }));
      }
      if (url.includes("/api/v1/binaries/1") && init?.method === "DELETE") {
        expect(url).toContain("confirm=test.exe");
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    const deleteButtons = await screen.findAllByRole("button", { name: "Delete" });
    const firstDelete = deleteButtons[0];
    if (!firstDelete) throw new Error("No Delete button found");
    await user.click(firstDelete);

    const confirmInput = await screen.findByLabelText(/binary name confirmation/i);
    const dialogDelete = () => {
      const buttons = screen.getAllByRole("button", { name: "Delete", hidden: true });
      const button = buttons.at(-1);
      if (!button) throw new Error("No dialog Delete button found");
      return button;
    };
    expect(dialogDelete()).toBeDisabled();

    await user.type(confirmInput, "wrong-name");
    expect(dialogDelete()).toBeDisabled();

    await user.clear(confirmInput);
    await user.type(confirmInput, "test.exe");
    expect(dialogDelete()).toBeEnabled();
    await user.click(dialogDelete());

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/binaries/1?confirm=test.exe"),
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });
});
