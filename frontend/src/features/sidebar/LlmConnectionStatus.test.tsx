import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { HealthDto } from "@/api/types";
import { HEALTH_QUERY_KEY } from "@/api/queries/health";
import { LlmConnectionStatus } from "./LlmConnectionStatus";

vi.mock("@/config/ConfigProvider", () => ({
  useConfig: () => ({
    adapters: { ghidra: "mock", llm: "litellm", llmModel: "openai/gpt-4o" },
  }),
}));

const healthy: HealthDto = {
  status: "ok",
  dbOk: true,
  migrationRevision: "0006",
  ghidraAdapter: "mock",
  llmAdapter: "litellm",
  llmHealth: { reachable: true, detail: null },
};

function renderWithHealth(health: HealthDto | undefined) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  if (health) queryClient.setQueryData(HEALTH_QUERY_KEY, health);
  return render(
    <QueryClientProvider client={queryClient}>
      <LlmConnectionStatus />
    </QueryClientProvider>,
  );
}

describe("LlmConnectionStatus", () => {
  it("shows that the active connector is connected", () => {
    renderWithHealth(healthy);

    expect(screen.getByText(/Connected — litellm/)).toBeInTheDocument();
    expect(screen.getByText("openai/gpt-4o")).toBeInTheDocument();
  });

  it("shows an unavailable connector and its diagnostic", () => {
    renderWithHealth({
      ...healthy,
      llmHealth: { reachable: false, detail: "invalid API key" },
    });

    expect(screen.getByText(/Unavailable — litellm/)).toBeInTheDocument();
    expect(screen.getByText("invalid API key")).toBeInTheDocument();
  });

  it("shows checking while health has not loaded", () => {
    renderWithHealth(undefined);

    expect(screen.getByText("LLM: litellm — checking…")).toBeInTheDocument();
  });
});