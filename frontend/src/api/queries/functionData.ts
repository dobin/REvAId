/**
 * `GET /functions/{id}/data`: PE data items a function accesses.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { FunctionDataDto, FunctionId } from "@/api/types";

const DATA_LIMIT = 200;

export function useFunctionDataQuery(functionId: FunctionId | null) {
  return useQuery({
    queryKey: ["function-data", functionId],
    queryFn: () =>
      apiClient.get<FunctionDataDto>(
        `/functions/${String(functionId)}/data?limit=${String(DATA_LIMIT)}`,
      ),
    enabled: functionId !== null,
  });
}
