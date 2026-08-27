import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "./Sidebar";

vi.mock("./LlmConnectionStatus", () => ({
  LlmConnectionStatus: () => <div>LLM connector status</div>,
}));

describe("Sidebar", () => {
  it("renders the binary section", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <Sidebar
          binaryName={null}
          binaryId={null}
          analysisImageBase={null}
          runtimeBase={null}
          onRuntimeBaseChange={() => undefined}
          viewId={null}
          onSelectView={() => undefined}
          onImported={() => undefined}
        />
      </QueryClientProvider>,
    );
    expect(screen.getByText("Binary")).toBeInTheDocument();
    expect(screen.getByText("LLM Connection")).toBeInTheDocument();
    expect(screen.getByText("LLM connector status")).toBeInTheDocument();
  });

  it("renders the binary name and view controls in the View section", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <Sidebar
          binaryName="test.exe"
          binaryId={1}
          analysisImageBase={0x400000}
          runtimeBase={null}
          onRuntimeBaseChange={() => undefined}
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
