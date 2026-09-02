/**
 * Toolbar mode badge (ADR 0006) — surfaces whether the instance is running
 * in public demo mode (each browser gets its own anonymous views) or private
 * single-user mode (views are shared). Reads the `publicMode` flag from
 * `GET /config` via `useConfig()`, the same single-payload contract every
 * other config consumer uses (E1d).
 */
import { useConfig } from "@/config/ConfigProvider";

const badgeStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "0.25rem",
  fontSize: "0.7rem",
  fontWeight: 600,
  padding: "0.125rem 0.5rem",
  borderRadius: "999px",
  border: "1px solid",
  whiteSpace: "nowrap",
};

export function ModeIndicator() {
  const { publicMode } = useConfig();

  if (publicMode) {
    return (
      <span
        style={{
          ...badgeStyle,
          color: "#92400e",
          borderColor: "#fbbf24",
          background: "#fef3c7",
        }}
        title="Public demo mode — each browser has its own private views; view listing is disabled."
      >
        ◉ Public
      </span>
    );
  }

  return (
    <span
      style={{
        ...badgeStyle,
        color: "#1d4ed8",
        borderColor: "#93c5fd",
        background: "#eff6ff",
      }}
      title="Private mode — single-user; views are shared across browsers."
    >
      ◉ Private
    </span>
  );
}
