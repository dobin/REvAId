import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfigProvider } from "@/config/ConfigProvider";
import { HealthPanel } from "./HealthPanel";
import type { AppConfigDto, HealthDto } from "@/api/types";

const config: AppConfigDto = {
  tableRowCap: 16,
  callerSuppressThreshold: 32,
  utilityFanInThreshold: 50,
  fanOutAllHardCap: 50,
  nodeCountSoftWarning: 150,
  cardWidthPx: 380,
  summaryConcurrency: 4,
  nodeColorPalette: ["slate", "red"],
  adapters: { ghidra: "mock", llm: "mock", llmModel: "mock-llm-v1" },
};

const health: HealthDto = {
  status: "ok",
  dbOk: true,
  migrationRevision: "0001",
  ghidraAdapter: "mock",
  llmAdapter: "mock",
};

function renderWithProviders() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ConfigProvider fallback={<p>loading</p>}>
        <HealthPanel />
      </ConfigProvider>
    </QueryClientProvider>,
  );
}

describe("HealthPanel", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = input instanceof Request ? input.url : String(input);
        if (url.endsWith("/api/v1/config")) {
          return Promise.resolve(new Response(JSON.stringify(config), { status: 200 }));
        }
        if (url.endsWith("/api/v1/health")) {
          return Promise.resolve(new Response(JSON.stringify(health), { status: 200 }));
        }
        return Promise.reject(new Error(`Unexpected fetch: ${url}`));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders config thresholds and health status once both resolve", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/tableRowCap: 16/)).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText(/status: ok/)).toBeInTheDocument();
    });
    expect(screen.getByText(/utilityFanInThreshold: 50/)).toBeInTheDocument();
  });
});
