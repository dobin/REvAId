/**
 * Orchestrates one direction (`callees` | `callers`) of a card's neighbour
 * tables (TAD §2.3/§4.3).
 *
 * `callersSuppressed` short-circuits to just `SuppressedNotice` (D7/E2a) —
 * filter/sort/utility-group (and therefore `VirtualRowList`'s demand
 * acquisition) never render for a suppressed caller table, matching the
 * backend's own "never fetch 291 rows" guarantee. A suppressed hub's own
 * card summary (priority 0, wired in `FunctionCardNode`) is still demanded —
 * only its caller *table* is inert.
 *
 * I9: row demand priority is 1 for the selected card's own tables, 2
 * otherwise (§5.1's priority ladder) — this is what makes "open a card,
 * analyse it first, then its neighbours" fall out of the existing queue
 * priorities rather than any client-side sequencing.
 */
import { useState } from "react";
import { useNeighboursQuery } from "@/api/queries/neighbours";
import type { FunctionId, ViewId } from "@/api/types";
import { useAppStore } from "@/store";
import { FilterInput } from "./FilterInput";
import { SortControl, type SortKey, type SortOrder } from "./SortControl";
import { SuppressedNotice } from "./SuppressedNotice";

import { UtilityGroup } from "./UtilityGroup";
import { VirtualRowList } from "./VirtualRowList";

export function NeighbourTable({
  functionId,
  viewId,
  direction,
}: {
  functionId: FunctionId;
  viewId: ViewId;
  direction: "callees" | "callers";
}) {
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<SortKey>("name");
  const [order, setOrder] = useState<SortOrder>("asc");
  const isSelected = useAppStore((s) => s.selectedFunctionId === functionId);
  const rowPriority = isSelected ? 1 : 2;

  const { data, isPending, isError } = useNeighboursQuery({
    functionId,
    viewId,
    direction,
    group: "primary",
    sort,
    order,
    filter: filter || undefined,
  });

  const label = direction === "callees" ? "Callees" : "Callers";
  // Fan-out provenance (D8): every row fans out from *this* card's function.
  // `direction` decides orientation — a callees row grows the canvas right
  // (`fanout`), a callers row grows it left (`fanin`) — resolved downstream
  // in `fanOutFunction`. Both share this same origin.
  const origin = { functionId, direction };

  if (isPending) return <p style={{ fontSize: "0.8125rem" }}>Loading {label.toLowerCase()}…</p>;
  if (isError) {
    return <p style={{ fontSize: "0.8125rem" }}>Could not load {label.toLowerCase()}.</p>;
  }

  if (direction === "callers" && data.callersSuppressed) {
    return (
      <section>
        <hr style={{ border: "none", borderTop: "1px solid #e5e7eb", margin: "0.5rem 0" }} />
        <h3 style={{ fontSize: "0.8125rem", margin: "0.5rem 0 0.25rem" }}>{label}</h3>
        <SuppressedNotice total={data.total} />
      </section>
    );
  }

  return (
    <section>
      <hr style={{ border: "none", borderTop: "1px solid #e5e7eb", margin: "0.5rem 0" }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h3 style={{ fontSize: "0.8125rem", margin: "0.5rem 0 0.25rem" }}>{label}</h3>
        <div style={{ display: "flex", gap: "0.375rem" }}>
          <FilterInput label={`Filter ${label.toLowerCase()}`} onFilterChange={setFilter} />
          <SortControl
            label={`Sort ${label.toLowerCase()}`}
            sort={sort}
            order={order}
            onSortChange={setSort}
            onOrderChange={setOrder}
          />
        </div>
      </div>
      <VirtualRowList
        rows={data.rows}
        origin={origin}
        demand={{ surface: `table:${String(functionId)}:${direction}:primary`, priority: rowPriority }}
      />
      <UtilityGroup
        functionId={functionId}
        viewId={viewId}
        direction={direction}
        totalUtility={data.totalUtility}
        priority={rowPriority}
      />
      {data.mayBeIncomplete && (
        <p style={{ fontSize: "0.6875rem", color: "#9ca3af", margin: "0.25rem 0 0" }}>
          List may be incomplete (indirect calls).
        </p>
      )}
    </section>
  );
}
