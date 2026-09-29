import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toolbar } from "./Toolbar";

// Toolbar renders ModeIndicator, which reads `publicMode` from useConfig().
vi.mock("@/config/ConfigProvider", () => ({
  useConfig: () => ({ publicMode: false }),
}));

describe("Toolbar", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the brand as a home link and the binary name", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Toolbar
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const homeLink = screen.getByText("GraphRev");
    expect(homeLink).toBeInTheDocument();
    expect(homeLink.closest("a")).toHaveAttribute("href", "/");
  });

  it("shows Explore and Search links for the current binary", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/sample.exe/search"]}>
          <Toolbar binaryName="sample.exe" />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("link", { name: "Explore" })).toHaveAttribute("href", "/sample.exe/");
    expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute("href", "/sample.exe/search");
    expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute("aria-current", "page");
  });
});
