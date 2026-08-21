/**
 * F1a / E1d: `GET /config` is the *only* place thresholds enter the client.
 * Fetched once at boot with `staleTime: Infinity`; children render only after
 * it resolves so no component ever has a reason to hard-code a default.
 */
import { createContext, useContext, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { AppConfigDto } from "@/api/types";

const ConfigContext = createContext<AppConfigDto | null>(null);

async function fetchConfig(): Promise<AppConfigDto> {
  return apiClient.get<AppConfigDto>("/config");
}

export function useConfigQuery() {
  return useQuery({
    queryKey: ["config"],
    queryFn: fetchConfig,
    staleTime: Number.POSITIVE_INFINITY,
  });
}

/** Throws if used before {@link ConfigProvider} has resolved — this is
 * intentional: no component may fall back to a hard-coded default (F1a). */
export function useConfig(): AppConfigDto {
  const config = useContext(ConfigContext);
  if (!config) {
    throw new Error("useConfig() called outside a resolved ConfigProvider.");
  }
  return config;
}

export function ConfigProvider({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback: ReactNode;
}) {
  const { data, isPending, isError, error } = useConfigQuery();

  if (isPending) return fallback;
  if (isError) throw error;

  return <ConfigContext.Provider value={data}>{children}</ConfigContext.Provider>;
}
