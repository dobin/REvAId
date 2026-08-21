/**
 * Generic empty-state slot — icon/text/optional-action. Used by
 * `CanvasEmptyState` and any "nothing here yet" surface.
 */
import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.5rem",
        padding: "2rem",
        textAlign: "center",
        color: "var(--gr-color-muted, #6b7280)",
      }}
    >
      <p style={{ fontWeight: 600, margin: 0 }}>{title}</p>
      {description && <p style={{ margin: 0, fontSize: "0.875rem" }}>{description}</p>}
      {action}
    </div>
  );
}
