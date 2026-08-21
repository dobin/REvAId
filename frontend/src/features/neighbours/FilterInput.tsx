/**
 * Per-table filter (D22) — substring over name + summaryShort. Debounced so
 * typing does not refetch on every keystroke.
 */
import { useEffect, useState } from "react";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const DEBOUNCE_MS = 250;

export function FilterInput({
  onFilterChange,
  label,
}: {
  onFilterChange: (value: string) => void;
  label: string;
}) {
  const [text, setText] = useState("");
  const debounced = useDebouncedValue(text, DEBOUNCE_MS);

  useEffect(() => {
    onFilterChange(debounced);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onFilterChange identity is not stable across renders in callers; debounced value is the true trigger.
  }, [debounced]);

  return (
    <input
      type="text"
      aria-label={label}
      placeholder="Filter…"
      value={text}
      onChange={(e) => {
        setText(e.target.value);
      }}
      style={{ fontSize: "0.75rem", padding: "0.125rem 0.375rem" }}
    />
  );
}
