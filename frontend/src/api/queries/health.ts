/**
 * `GET /health` exposes the active LLM adapter's own reachability check.
 * This is intentionally independent of the queue: an empty queue does not
 * establish that the configured connector can accept a summary request.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { HealthDto } from "@/api/types";

export const HEALTH_QUERY_KEY = ["health"] as const;

async function fetchHealth(): Promise<HealthDto> {
  return apiClient.get<HealthDto>("/health");
}

export function useHealthQuery() {
  return useQuery({
    queryKey: HEALTH_QUERY_KEY,
    queryFn: fetchHealth,
    // Unlike queue transitions, connector health has no SSE event. Poll as a
    // lightweight fallback so a recovered provider becomes visible promptly.
    refetchInterval: 15_000,
  });
}