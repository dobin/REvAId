/** Displays passive worker evidence and an explicit, live LLM test action. */
import { useLlmProbeMutation, useLlmStatusQuery } from "@/api/queries/llmStatus";
import { useConfig } from "@/config/ConfigProvider";

const labelStyle: React.CSSProperties = {
  fontSize: "0.75rem",
  lineHeight: 1.4,
};

const detailStyle: React.CSSProperties = {
  ...labelStyle,
  color: "#6b7280",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export function LlmConnectionStatus() {
  const { adapters } = useConfig();
  const { data, isError, isPending } = useLlmStatusQuery();
  const probe = useLlmProbeMutation();
  const adapter = data?.adapter ?? adapters.llm;

  if (isPending) {
    return <p style={labelStyle}>LLM: {adapter} — loading worker status…</p>;
  }

  if (isError || !data) {
    return <p style={{ ...labelStyle, color: "#b45309" }}>● LLM worker status unavailable</p>;
  }

  const outcome = {
    success: { label: "Last summary succeeded", color: "#15803d" },
    failure: { label: "Last summary failed", color: "#b91c1c" },
    rate_limited: { label: "Provider rate limited", color: "#b45309" },
    no_outcome: { label: "No worker outcome yet", color: "#6b7280" },
  }[data.outcome];

  return (
    <div>
      <p style={{ ...labelStyle, margin: 0, color: outcome.color }}>
        ● {outcome.label} — {adapter}
      </p>
      <p style={{ ...detailStyle, margin: "0.125rem 0 0" }} title={data.model}>
        {data.model}
      </p>
      {data.observedAt && <p style={{ ...detailStyle, margin: "0.125rem 0 0" }}>Observed {data.observedAt}</p>}
      {data.errorCode && (
        <p style={{ ...detailStyle, color: outcome.color, margin: "0.125rem 0 0" }}>
          {data.errorCode}
        </p>
      )}
      <button
        type="button"
        disabled={probe.isPending}
        onClick={() => {
          probe.mutate();
        }}
      >
        {probe.isPending ? "Testing connection…" : "Test connection"}
      </button>
      {probe.isSuccess && (
        <p style={{ ...detailStyle, color: probe.data.reachable ? "#15803d" : "#b91c1c", margin: "0.125rem 0 0" }}>
          {probe.data.reachable ? "Live connection test succeeded." : `Live connection test failed: ${probe.data.detail ?? "unknown error"}`}
        </p>
      )}
      {probe.isError && (
        <p style={{ ...detailStyle, color: "#b91c1c", margin: "0.125rem 0 0" }}>
          Live connection test could not be completed.
        </p>
      )}
    </div>
  );
}