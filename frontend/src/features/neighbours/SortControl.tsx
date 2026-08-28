/**
 * Sort control (D23) — sort key + direction toggle for a neighbour table.
 */
import { Glyph } from "@/components/Glyph";

export type SortKey = "callOrder" | "name" | "address" | "fanIn";
export type SortOrder = "asc" | "desc";

export function SortControl({
  sort,
  order,
  onSortChange,
  onOrderChange,
  label,
  direction,
}: {
  sort: SortKey;
  order: SortOrder;
  onSortChange: (sort: SortKey) => void;
  onOrderChange: (order: SortOrder) => void;
  label: string;
  direction: "callees" | "callers";
}) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
      <select
        aria-label={label}
        value={sort}
        onChange={(e) => {
          onSortChange(e.target.value as SortKey);
        }}
        style={{ fontSize: "0.75rem" }}
      >
        {direction === "callees" && <option value="callOrder">Position</option>}
        <option value="name">Name</option>
        <option value="address">Address</option>
        <option value="fanIn">Fan-in</option>
      </select>
      <button
        type="button"
        aria-label={`${label} direction`}
        onClick={() => {
          onOrderChange(order === "asc" ? "desc" : "asc");
        }}
      >
        <Glyph name={order === "asc" ? "sortAsc" : "sortDesc"} />
      </button>
    </span>
  );
}
