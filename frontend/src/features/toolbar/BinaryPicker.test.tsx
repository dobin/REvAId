import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BinaryPicker } from "./BinaryPicker";
import type { BinarySummaryDto } from "@/api/types";

const binaries: BinarySummaryDto[] = [
  {
    id: 1,
    name: "acme.exe",
    version: "1.0",
    functionCount: 180,
    edgeCount: 400,
    lastViewId: null,
    createdAt: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "libparse.dll",
    version: "1.0",
    functionCount: 60,
    edgeCount: 90,
    lastViewId: null,
    createdAt: "2026-01-01T00:00:00Z",
  },
];

function renderWithProviders(value: number | null, onChange: (id: number) => void) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <BinaryPicker value={value} onChange={onChange} />
    </QueryClientProvider>,
  );
}

describe("BinaryPicker", () => {
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

  it("shows a loading state, then the binary options", async () => {
    renderWithProviders(null, vi.fn());
    expect(screen.getByText(/loading binaries/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Binary" })).toBeInTheDocument();
    });
  });

  it("shows an empty message when there are no binaries", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))),
    );
    renderWithProviders(null, vi.fn());

    await waitFor(() => {
      expect(screen.getByText(/no binaries ingested yet/i)).toBeInTheDocument();
    });
  });
});
