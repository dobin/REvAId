/**
 * Orchestrates one direction (`callees` | `callers`) of a card's neighbour
 * tables (TAD §2.3/§4.3). Side-effect free (C2c) — a GET only, no summary
 * demand wiring in I5.
 *
 * `callersSuppressed` short-circuits to just `SuppressedNotice` (D7/E2a) —
 * filter/sort/utility-group never render for a suppressed caller table,
 * matching the backend's own "never fetch 291 rows" guarantee.
 */
import { useState } from "react";
import { useNeighboursQuery } from "@/api/queries/neighbours";
import type { FunctionId, ViewId } from "@/api/types";
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
      <VirtualRowList rows={data.rows} origin={origin} />
      <UtilityGroup
        functionId={functionId}
        viewId={viewId}
        direction={direction}
        totalUtility={data.totalUtility}
      />
      {data.mayBeIncomplete && (
        <p style={{ fontSize: "0.6875rem", color: "#9ca3af", margin: "0.25rem 0 0" }}>
          List may be incomplete (indirect calls).
        </p>
      )}
    </section>
  );
}
