import { render, screen, waitFor } from "@testing-library/react";
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

  it("renders the brand and the binary picker", async () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <Toolbar selectedBinaryId={null} onSelectBinary={vi.fn()} />
      </QueryClientProvider>,
    );

    expect(screen.getByText("GraphRev")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/no binaries ingested yet/i)).toBeInTheDocument();
    });
  });
});
