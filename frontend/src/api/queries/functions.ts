/**
 * `GET /functions/{id}` (E1).
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { FunctionDto, FunctionId } from "@/api/types";

async function fetchFunction(functionId: FunctionId): Promise<FunctionDto> {
  return apiClient.get<FunctionDto>(`/functions/${String(functionId)}`);
}

export function useFunctionQuery(functionId: FunctionId | null) {
  return useQuery({
    queryKey: ["function", functionId],
    queryFn: () => fetchFunction(functionId as FunctionId),
    enabled: functionId !== null,
  });
}
