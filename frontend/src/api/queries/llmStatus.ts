/** Passive worker status plus the user-triggered, live LLM probe. */
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { LlmProbeDto, LlmStatusDto } from "@/api/types";

export const LLM_STATUS_QUERY_KEY = ["llm-status"] as const;

export function useLlmStatusQuery() {
  return useQuery({
    queryKey: LLM_STATUS_QUERY_KEY,
    queryFn: () => apiClient.get<LlmStatusDto>("/llm-status"),
  });
}

export function useLlmProbeMutation() {
  return useMutation({
    mutationFn: () => apiClient.post<LlmProbeDto>("/llm-status/probe"),
  });
}