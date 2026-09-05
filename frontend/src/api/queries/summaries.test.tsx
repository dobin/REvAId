/**
 * Summary-demand mutations publish queue SSE events. They must not invalidate
 * the queue query individually: a card-heavy view creates many mutations,
 * and invalidating the active shared query after each one causes a GET
 * /queue request storm. Reconnection remains the authoritative refetch path.
 */
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { QueueSnapshotDto } from "@/api/types";
import { QUEUE_QUERY_KEY } from "./queue";
import { useDemandSummaryMutation, useReleaseSummaryDemandMutation } from "./summaries";

const queueSnapshot: QueueSnapshotDto = {
  inFlight: [],
  queued: [],
  inFlightCount: 0,
  queuedCount: 0,
  pausedUntil: null,
};

function requestUrl(input: string | URL | Request): string {
  return input instanceof Request ? input.url : String(input);
}

function queueRequestCount(): number {
  return vi.mocked(global.fetch).mock.calls.filter(([input]) =>
    requestUrl(input).endsWith("/api/v1/queue"),
  ).length;
}

function wrapperFor(queryClient: QueryClient) {
  return function QueryClientWrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("summary demand queue synchronization", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not refetch the queue once per successful demand or release", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = requestUrl(input);
        if (url.endsWith("/api/v1/queue")) {
          return Promise.resolve(new Response(JSON.stringify(queueSnapshot), { status: 200 }));
        }
        if (url.includes("/summary")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                functionId: 1,
                summaryStatus: "pending",
                queuePosition: 0,
                summaryShort: null,
              }),
              { status: 202 },
            ),
          );
        }
        return Promise.reject(new Error(`Unexpected fetch: ${url}`));
      }),
    );

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = wrapperFor(queryClient);
    const queue = renderHook(
      () =>
        useQuery({
          queryKey: QUEUE_QUERY_KEY,
          queryFn: () => fetch("/api/v1/queue").then((response) => response.json()),
        }),
      { wrapper },
    );
    const mutations = renderHook(
      () => ({ demand: useDemandSummaryMutation(), release: useReleaseSummaryDemandMutation() }),
      { wrapper },
    );

    await waitFor(() => { expect(queue.result.current.isSuccess).toBe(true); });
    expect(queueRequestCount()).toBe(1);

    await Promise.all(
      Array.from({ length: 24 }, (_, index) =>
        mutations.result.current.demand.mutateAsync({ functionId: index + 1, priority: 0 }),
      ),
    );
    await Promise.all(
      Array.from({ length: 24 }, (_, index) =>
        mutations.result.current.release.mutateAsync(index + 1),
      ),
    );

    expect(queueRequestCount()).toBe(1);
  });
});