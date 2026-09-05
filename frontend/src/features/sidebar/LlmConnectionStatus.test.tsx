import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { LlmStatusDto } from "@/api/types";
import { LLM_STATUS_QUERY_KEY } from "@/api/queries/llmStatus";
import { LlmConnectionStatus } from "./LlmConnectionStatus";

vi.mock("@/config/ConfigProvider", () => ({
  useConfig: () => ({
    adapters: { ghidra: "mock", llm: "litellm", llmModel: "openai/gpt-4o" },
  }),
}));

const succeeded: LlmStatusDto = {
  adapter: "litellm",
  model: "openai/gpt-4o",
  outcome: "success",
  observedAt: "2026-09-05T12:00:00+00:00",
  errorCode: null,
};

function renderWithStatus(status: LlmStatusDto | undefined) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  if (status) queryClient.setQueryData(LLM_STATUS_QUERY_KEY, status);
  return render(
    <QueryClientProvider client={queryClient}>
      <LlmConnectionStatus />
    </QueryClientProvider>,
  );
}

describe("LlmConnectionStatus", () => {
  it("shows the last successful worker outcome rather than live connectivity", () => {
    renderWithStatus(succeeded);

    expect(screen.getByText(/Last summary succeeded — litellm/)).toBeInTheDocument();
    expect(screen.getByText("openai/gpt-4o")).toBeInTheDocument();
    expect(screen.getByText(/Observed 2026-09-05/)).toBeInTheDocument();
  });

  it("shows a rate-limited worker result and its safe error code", () => {
    renderWithStatus({
      ...succeeded,
      outcome: "rate_limited",
      errorCode: "SUMMARY_RATE_LIMITED",
    });

    expect(screen.getByText(/Provider rate limited — litellm/)).toBeInTheDocument();
    expect(screen.getByText("SUMMARY_RATE_LIMITED")).toBeInTheDocument();
  });

  it("shows no-outcome status for a current configuration with no worker work", () => {
    renderWithStatus({ ...succeeded, outcome: "no_outcome", observedAt: null });

    expect(screen.getByText(/No worker outcome yet — litellm/)).toBeInTheDocument();
  });

  it("shows loading while passive status has not loaded", () => {
    renderWithStatus(undefined);

    expect(screen.getByText("LLM: litellm — loading worker status…")).toBeInTheDocument();
  });

  it("does not probe until the user explicitly tests the connection", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ reachable: true, detail: null }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithStatus(succeeded);

    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/llm-status/probe",
        expect.objectContaining({ method: "POST" }),
      );
    });
    vi.unstubAllGlobals();
  });
});