import { useHealthQuery } from "@/api/queries/health";
import { useConfig } from "@/config/ConfigProvider";

const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(13rem, 1fr))",
  gap: "0.75rem",
};

const cardStyle: React.CSSProperties = {
  minWidth: 0,
  padding: "0.875rem 1rem",
  border: "1px solid #e5e7eb",
  borderRadius: "0.625rem",
  background: "#f9fafb",
};

const labelStyle: React.CSSProperties = {
  margin: 0,
  fontSize: "0.7rem",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "var(--gr-color-muted, #6b7280)",
};

const valueStyle: React.CSSProperties = {
  margin: "0.375rem 0 0",
  fontSize: "0.875rem",
  fontWeight: 600,
  color: "var(--gr-color-ground-truth, #111827)",
};

const detailStyle: React.CSSProperties = {
  margin: "0.25rem 0 0",
  overflow: "hidden",
  color: "var(--gr-color-muted, #6b7280)",
  fontFamily: "var(--gr-font-mono, monospace)",
  fontSize: "0.75rem",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export function ConfigurationOverview() {
  const { adapters, publicMode } = useConfig();
  const { data: health, isPending, isError } = useHealthQuery();

  let decompilerValue = "Checking…";
  let decompilerDetail = "Verifying the configured Kuna executable";
  if (isError) {
    decompilerValue = "Unknown";
    decompilerDetail = "Health check unavailable";
  } else if (!isPending) {
    decompilerValue = health.decompilerHealth.reachable ? "Available" : "Unavailable";
    decompilerDetail = health.decompilerHealth.detail ?? "No details reported";
  }

  return (
    <section aria-labelledby="configuration-heading">
      <h2 id="configuration-heading" style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>
        Configuration
      </h2>
      <div style={gridStyle}>
        <div style={cardStyle}>
          <p style={labelStyle}>LLM</p>
          <p style={valueStyle}>{adapters.llm}</p>
          <p style={detailStyle} title={adapters.llmModel}>{adapters.llmModel}</p>
        </div>
        <div style={cardStyle}>
          <p style={labelStyle}>Decompiler</p>
          <p style={valueStyle}>{decompilerValue}</p>
          <p style={detailStyle} title={decompilerDetail}>{decompilerDetail}</p>
        </div>
        <div style={cardStyle}>
          <p style={labelStyle}>Public mode</p>
          <p style={valueStyle}>{publicMode ? "On" : "Off"}</p>
          <p style={detailStyle}>{publicMode ? "Anonymous private views" : "Shared single-user views"}</p>
        </div>
      </div>
    </section>
  );
}
