import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toolbar } from "./Toolbar";

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
            binaryName="test.exe"
            binaryId={null}
            selectedViewId={null}
            onSelectView={vi.fn()}
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const homeLink = screen.getByText("GraphRev");
    expect(homeLink).toBeInTheDocument();
    expect(homeLink.closest("a")).toHaveAttribute("href", "/");
    expect(screen.getByText("test.exe")).toBeInTheDocument();
  });
});
