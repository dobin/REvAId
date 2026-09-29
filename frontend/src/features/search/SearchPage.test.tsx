import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { SearchPage } from "./SearchPage";

vi.mock("./FunctionSearchPanel", () => ({
  FunctionSearchPanel: ({
    onAdded,
    onOpenExisting,
  }: {
    onAdded?: () => void;
    onOpenExisting?: (functionId: number) => void;
  }) => (
    <>
      <button type="button" onClick={() => { onAdded?.(); }}>Add function</button>
      <button type="button" onClick={() => { onOpenExisting?.(9); }}>Open existing function</button>
    </>
  ),
}));

function CurrentPath() {
  const location = useLocation();
  return (
    <>
      <output aria-label="Current path">{location.pathname}</output>
      <output aria-label="Navigation state">{JSON.stringify(location.state)}</output>
    </>
  );
}

describe("SearchPage", () => {
  it("is a dedicated full-width page and returns to the binary Explore route after Add", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/sample.exe/search"]}>
          <Routes>
            <Route path="/sample.exe/search" element={
              <SearchPage
                binaryId={1}
                binaryName="sample.exe"
                viewId={4}
                analysisImageBase={null}
                runtimeBase={null}
              />
            } />
            <Route path="/sample.exe/" element={<p>Explore canvas</p>} />
          </Routes>
          <CurrentPath />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const page = screen.getByRole("main");
    expect(page).toHaveStyle({ flex: "1 1 0%" });
    expect(screen.getByRole("heading", { name: "Search functions" })).toBeInTheDocument();
    expect(screen.getByLabelText("Current path")).toHaveTextContent("/sample.exe/search");

    fireEvent.click(screen.getByRole("button", { name: "Add function" }));
    expect(screen.getByText("Explore canvas")).toBeInTheDocument();
    expect(screen.getByLabelText("Current path")).toHaveTextContent("/sample.exe/");
    expect(screen.getByLabelText("Navigation state")).toHaveTextContent("null");
  });

  it("returns to Explore with the existing function ID to focus, without selecting details", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/sample.exe/search"]}>
          <Routes>
            <Route path="/sample.exe/search" element={
              <SearchPage
                binaryId={1}
                binaryName="sample.exe"
                viewId={4}
                analysisImageBase={null}
                runtimeBase={null}
              />
            } />
            <Route path="/sample.exe/" element={<p>Explore canvas</p>} />
          </Routes>
          <CurrentPath />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open existing function" }));
    expect(screen.getByText("Explore canvas")).toBeInTheDocument();
    expect(screen.getByLabelText("Current path")).toHaveTextContent("/sample.exe/");
    expect(screen.getByLabelText("Navigation state")).toHaveTextContent('{"focusFunctionId":9}');
  });
});
