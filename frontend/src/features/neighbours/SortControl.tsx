/**
 * Sort control (D23) — sort key + direction toggle for a neighbour table.
 */
import { Glyph } from "@/components/Glyph";

export type SortKey = "name" | "address" | "fanIn";
export type SortOrder = "asc" | "desc";

export function SortControl({
  sort,
  order,
  onSortChange,
  onOrderChange,
  label,
}: {
  sort: SortKey;
  order: SortOrder;
  onSortChange: (sort: SortKey) => void;
  onOrderChange: (order: SortOrder) => void;
  label: string;
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
        <Glyph name="sort" /> {order}
      </button>
    </span>
  );
}
