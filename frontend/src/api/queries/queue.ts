/**
 * `GET /queue` + `POST /queue/cancel-pending` (TAD §4.2 endpoints 20-21, I8).
 * The chip's `GET /queue` cache entry is kept fresh by `SseProvider` patching
 * it in place on every `queue` SSE event (E5b) — this module supplies the
 * initial fetch and the cancel mutation only.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { CancelPendingResponseDto, QueueSnapshotDto } from "@/api/types";

async function fetchQueue(): Promise<QueueSnapshotDto> {
  return apiClient.get<QueueSnapshotDto>("/queue");
}

export const QUEUE_QUERY_KEY = ["queue"] as const;

export function useQueueQuery() {
  return useQuery({
    queryKey: QUEUE_QUERY_KEY,
    queryFn: fetchQueue,
    // The SSE `queue` event only carries counters (E5b), not the full
    // listing the popover shows — refetch periodically as a fallback for
    // browsers/tabs where the SSE connection is degraded, without relying
    // on it as the primary update path.
    refetchInterval: 15_000,
  });
}

export function useCancelPendingMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<CancelPendingResponseDto>("/queue/cancel-pending"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUEUE_QUERY_KEY });
    },
  });
}
