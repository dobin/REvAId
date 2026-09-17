import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Sidebar } from "./Sidebar";

const configMock = vi.hoisted(() => ({ publicMode: false }));

// ViewPicker reads `publicMode` from useConfig() (ADR 0006) — mock the
// provider rather than fetching a real config for this layout test.
vi.mock("@/config/ConfigProvider", () => ({
  useConfig: () => configMock,
}));

vi.mock("./LlmConnectionStatus", () => ({
  LlmConnectionStatus: () => <div>LLM connector status</div>,
}));

vi.mock("./ImportBinaryButton", () => ({
  ImportBinaryButton: () => <button type="button">(Re) Import binary</button>,
}));

vi.mock("./ResetSummariesButton", () => ({
  ResetSummariesButton: () => <button type="button">Reset summaries</button>,
}));

describe("Sidebar", () => {
  beforeEach(() => {
    configMock.publicMode = false;
  });

  it("renders persistent sidebar sections without a selected binary", () => {
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
    expect(screen.getByText("LLM Connection")).toBeInTheDocument();
    expect(screen.getByText("LLM connector status")).toBeInTheDocument();
  });

  it("renders the binary name in Image and view controls in View", () => {
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

    expect(screen.getByText("Image")).toBeInTheDocument();
    expect(screen.getByText("Binary: test.exe")).toBeInTheDocument();
    expect(screen.getByText("View")).toBeInTheDocument();
  });

  it("hides the View section in public mode", () => {
    configMock.publicMode = true;
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

    expect(screen.queryByText("View")).not.toBeInTheDocument();
  });

  it("hides binary import and summary reset actions in public mode", () => {
    configMock.publicMode = true;
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <Sidebar
          binaryName="test.exe"
          binaryId={1}
          analysisImageBase={0x400000}
          runtimeBase={null}
          onRuntimeBaseChange={() => undefined}
          viewId={5}
          onSelectView={vi.fn()}
          onImported={() => undefined}
        />
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("button", { name: "(Re) Import binary" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reset summaries" })).not.toBeInTheDocument();
  });
});
