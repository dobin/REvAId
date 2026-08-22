/**
 * `GET /functions/{id}` (E1).
 */
import { queryOptions, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { FunctionDto, FunctionId } from "@/api/types";

async function fetchFunction(functionId: FunctionId): Promise<FunctionDto> {
  return apiClient.get<FunctionDto>(`/functions/${String(functionId)}`);
}

/**
 * Shared options so `useFunctionQuery` and any `prefetchQuery` call site
 * (see `CanvasView.fanOutFunction`) provably hit the same cache entry — a
 * hand-duplicated, subtly different key would warm nothing and the prefetch
 * would silently do no good.
 */
export function functionQueryOptions(functionId: FunctionId) {
  return queryOptions({
    queryKey: ["function", functionId],
    queryFn: () => fetchFunction(functionId),
  });
}

export function useFunctionQuery(functionId: FunctionId | null) {
  return useQuery({
    ...functionQueryOptions(functionId as FunctionId),
    enabled: functionId !== null,
  });
}
