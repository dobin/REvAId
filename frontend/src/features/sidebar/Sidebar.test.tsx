import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  it("renders the legend heading", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <Sidebar
          binaryName={null}
          binaryId={null}
          viewId={null}
          onSelectView={() => undefined}
          onImported={() => undefined}
        />
      </QueryClientProvider>,
    );
    expect(screen.getByText("Legend")).toBeInTheDocument();
  });

  it("renders the binary name and view controls in the View section", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <Sidebar
          binaryName="test.exe"
          binaryId={1}
          viewId={null}
          onSelectView={vi.fn()}
          onImported={() => undefined}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByText("View")).toBeInTheDocument();
    expect(screen.getByText("test.exe")).toBeInTheDocument();
  });
});
