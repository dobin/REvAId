import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  it("renders the legend heading", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <Sidebar binaryId={null} viewId={null} onImported={() => undefined} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("Legend")).toBeInTheDocument();
  });
});
