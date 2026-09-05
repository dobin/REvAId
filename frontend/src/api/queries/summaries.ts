/**
 * `POST /functions/{id}/summary`, `DELETE /functions/{id}/summary`,
 * `POST /functions/{id}/summary/regenerate` (TAD §4.2 endpoints 17-19).
 *
 * These are plain mutations, not yet wired to any auto-demand trigger — the
 * demand *registry* (deciding WHEN to call `demandSummary`/`releaseSummary`
 * as cards/rows mount and unmount) is I9 scope (`store/demandSlice.ts`,
 * `hooks/useSummaryDemand.ts`). I8 only needs `demandSummary` to exist so a
 * manual "regenerate" affordance and future demand hook have something to
 * call, and so `SseProvider`'s reconnect reconciliation has a `queue`
 * invalidation target consistent with this module's mutations.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type {
  BinaryId,
  FunctionId,
  SummaryDemandRequest,
  SummaryDemandResponseDto,
} from "@/api/types";

async function demandSummary(
  functionId: FunctionId,
  request: SummaryDemandRequest,
): Promise<SummaryDemandResponseDto> {
  return apiClient.post<SummaryDemandResponseDto>(
    `/functions/${String(functionId)}/summary`,
    request,
  );
}

export function useDemandSummaryMutation() {
  return useMutation({
    mutationFn: ({ functionId, ...request }: { functionId: FunctionId } & SummaryDemandRequest) =>
      demandSummary(functionId, request),
  });
}

export function useReleaseSummaryDemandMutation() {
  return useMutation({
    mutationFn: (functionId: FunctionId) =>
      apiClient.delete<undefined>(`/functions/${String(functionId)}/summary`),
  });
}

export function useRegenerateSummaryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (functionId: FunctionId) =>
      apiClient.post<SummaryDemandResponseDto>(
        `/functions/${String(functionId)}/summary/regenerate`,
      ),
    onSuccess: (_result, functionId) => {
      void queryClient.invalidateQueries({ queryKey: ["function", functionId] });
    },
  });
}

/**
 * `DELETE /binaries/{id}/summaries` — TESTING affordance: nulls every
 * `summary_short`/`summary_long` (and status/model/... metadata) on every
 * function of the binary. Invalidates all function queries broadly since
 * every function of the binary is affected.
 */
export function useClearBinarySummariesMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (binaryId: BinaryId) =>
      apiClient.delete(`/binaries/${String(binaryId)}/summaries`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["function"] });
    },
  });
}
