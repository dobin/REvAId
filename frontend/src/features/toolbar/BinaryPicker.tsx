/**
 * Binary picker (E1) — the only functional toolbar piece in I5. ViewPicker
 * (I6, needs multi-view CRUD) and QueueChip (I7, needs the summary queue)
 * are deferred.
 */
import * as Select from "@radix-ui/react-select";
import { useBinariesQuery } from "@/api/queries/binaries";
import type { BinaryId } from "@/api/types";

export function BinaryPicker({
  value,
  onChange,
}: {
  value: BinaryId | null;
  onChange: (binaryId: BinaryId) => void;
}) {
  const { data: binaries, isPending, isError } = useBinariesQuery();

  if (isPending) return <span>Loading binaries…</span>;
  if (isError) return <span>Could not load binaries.</span>;
  if (binaries.length === 0) return <span>No binaries ingested yet.</span>;

  return (
    <Select.Root
      value={value !== null ? String(value) : ""}
      onValueChange={(next) => {
        onChange(Number(next));
      }}
    >
      <Select.Trigger aria-label="Binary" style={{ minWidth: "10rem" }}>
        <Select.Value placeholder="Select a binary…" />
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          position="popper"
          sideOffset={4}
          style={{
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            borderRadius: "0.375rem",
            boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
            minWidth: "var(--radix-select-trigger-width)",
            zIndex: 9999,
            overflow: "hidden",
          }}
        >
          <Select.Viewport style={{ padding: "0.25rem" }}>
            {binaries.map((binary) => (
              <Select.Item
                key={binary.id}
                value={String(binary.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "0.375rem 0.625rem",
                  borderRadius: "0.25rem",
                  cursor: "pointer",
                  outline: "none",
                  userSelect: "none",
                  fontFamily: "var(--gr-font-mono)",
                  fontSize: "0.875rem",
                  color: "var(--gr-color-ground-truth)",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = "#f3f4f6";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = "transparent";
                }}
              >
                <Select.ItemText>
                  {binary.name}{" "}
                  <span style={{ color: "var(--gr-color-muted)", fontSize: "0.8em" }}>
                    ({binary.functionCount} functions)
                  </span>
                </Select.ItemText>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
