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
        <Select.Content>
          <Select.Viewport>
            {binaries.map((binary) => (
              <Select.Item key={binary.id} value={String(binary.id)}>
                <Select.ItemText>
                  {binary.name} ({binary.functionCount} functions)
                </Select.ItemText>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
