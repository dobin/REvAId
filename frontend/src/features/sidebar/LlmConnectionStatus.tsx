/** Displays the configured LLM connector and its live reachability probe. */
import { useHealthQuery } from "@/api/queries/health";
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
  const { data, isError, isPending } = useHealthQuery();
  const adapter = data?.llmAdapter ?? adapters.llm;

  if (isPending) {
    return <p style={labelStyle}>LLM: {adapter} — checking…</p>;
  }

  if (isError || !data) {
    return <p style={{ ...labelStyle, color: "#b45309" }}>● LLM status unavailable</p>;
  }

  const connected = data.llmHealth.reachable;
  return (
    <div>
      <p style={{ ...labelStyle, margin: 0, color: connected ? "#15803d" : "#b91c1c" }}>
        ● {connected ? "Connected" : "Unavailable"} — {adapter}
      </p>
      <p style={{ ...detailStyle, margin: "0.125rem 0 0" }} title={adapters.llmModel}>
        {adapters.llmModel}
      </p>
      {!connected && data.llmHealth.detail && (
        <p style={{ ...detailStyle, color: "#b91c1c", margin: "0.125rem 0 0" }} title={data.llmHealth.detail}>
          {data.llmHealth.detail}
        </p>
      )}
    </div>
  );
}