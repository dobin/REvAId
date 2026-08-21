/**
 * Proves end-to-end wiring for `just dev` (F3 exit test): shows live
 * `/health` and `/config` data so a fresh clone can be visually verified
 * without needing the canvas (which arrives in I5).
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import type { HealthDto } from "@/api/types";
import { useConfig } from "@/config/ConfigProvider";

async function fetchHealth(): Promise<HealthDto> {
  return apiClient.get<HealthDto>("/health");
}

export function HealthPanel() {
  const config = useConfig();
  const { data: health, isPending, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
  });

  return (
    <div className="gr-ground-truth" style={{ padding: "1rem", fontSize: "0.875rem" }}>
      <h1 style={{ fontFamily: "var(--gr-font-sans)", fontSize: "1.25rem" }}>GraphRev</h1>

      <section>
        <h2>Health</h2>
        {isPending && <p>Loading…</p>}
        {isError && <p>Backend unreachable.</p>}
        {health && (
          <ul>
            <li>status: {health.status}</li>
            <li>dbOk: {String(health.dbOk)}</li>
            <li>migrationRevision: {health.migrationRevision}</li>
            <li>ghidraAdapter: {health.ghidraAdapter}</li>
            <li>llmAdapter: {health.llmAdapter}</li>
          </ul>
        )}
      </section>

      <section>
        <h2>Config (F1a)</h2>
        <ul>
          <li>tableRowCap: {config.tableRowCap}</li>
          <li>callerSuppressThreshold: {config.callerSuppressThreshold}</li>
          <li>utilityFanInThreshold: {config.utilityFanInThreshold}</li>
          <li>fanOutAllHardCap: {config.fanOutAllHardCap}</li>
          <li>nodeCountSoftWarning: {config.nodeCountSoftWarning}</li>
          <li>adapters: {config.adapters.ghidra} / {config.adapters.llm}</li>
        </ul>
      </section>
    </div>
  );
}
