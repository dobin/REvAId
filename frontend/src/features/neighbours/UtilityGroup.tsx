/**
 * "▸ ▫ utility calls (N)" collapsed group (D34). Expanding fetches the
 * `group=utility` page for the first time. Its rows acquire summary demand
 * only while expanded, so collapsing releases unstarted work.
 */
import { useState } from "react";
import { Glyph } from "@/components/Glyph";
import { useConfig } from "@/config/ConfigProvider";
import { useInfiniteNeighboursQuery } from "@/api/queries/neighbours";
import type { FunctionId, Priority, ViewId } from "@/api/types";
import type { FanOutOrigin } from "@/features/canvas/CanvasActions";
import { VirtualRowList } from "./VirtualRowList";
import { TableFooter } from "./TableFooter";
import type { SortKey, SortOrder } from "./SortControl";

export function UtilityGroup({
  functionId,
  viewId,
  direction,
  totalUtility,
  priority,
  sort,
  order,
}: {
  functionId: FunctionId;
  viewId: ViewId;
  direction: "callees" | "callers";
  totalUtility: number;
  priority: Priority;
  sort?: SortKey;
  order?: SortOrder;
}) {
  // Utility rows fan out exactly like primary rows: from this card, oriented
  // by direction (callees -> right, callers -> left). Resolved downstream.
  const origin: FanOutOrigin = { functionId, direction };
  const [expanded, setExpanded] = useState(false);

  if (totalUtility === 0) return null;

  return (
    <div>
      <button
        type="button"
        onClick={() => {
          setExpanded((prev) => !prev);
        }}
        aria-expanded={expanded}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.375rem",
          fontSize: "0.8125rem",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: "0.25rem 0",
        }}
      >
        <Glyph name={expanded ? "expand" : "expandCollapsed"} />
        <Glyph name="utility" /> utility calls ({totalUtility})
      </button>
      {expanded && (
        <UtilityGroupRows
          functionId={functionId}
          viewId={viewId}
          direction={direction}
          origin={origin}
          priority={priority}
          sort={sort ?? (direction === "callees" ? "callOrder" : "name")}
          order={order ?? "asc"}
        />
      )}
    </div>
  );
}

function UtilityGroupRows({
  functionId,
  viewId,
  direction,
  origin,
  priority,
  sort,
  order,
}: {
  functionId: FunctionId;
  viewId: ViewId;
  direction: "callees" | "callers";
  origin?: FanOutOrigin | undefined;
  priority: Priority;
  sort: SortKey;
  order: SortOrder;
}) {
  const config = useConfig();
  const { data, isPending, isError, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteNeighboursQuery({
    functionId,
    viewId,
    direction,
    group: "utility",
    limit: direction === "callers" ? 5 : config.tableRowCap,
    sort,
    order,
  });

  if (isPending) return <p style={{ fontSize: "0.75rem" }}>Loading…</p>;
  if (isError) return <p style={{ fontSize: "0.75rem" }}>Could not load utility calls.</p>;
  if (!data) return null;
  const firstPage = data.pages[0];
  if (!firstPage) return null;
  const rows = data.pages.flatMap((page) => page.rows);
  return (
    <>
      <VirtualRowList
        rows={rows}
        origin={origin}
        demand={{ surface: `table:${String(functionId)}:${direction}:utility`, priority }}
      />
      <TableFooter
        shown={rows.length}
        total={firstPage.total}
        isLoadingMore={isFetchingNextPage}
        {...(hasNextPage ? { onLoadMore: () => void fetchNextPage() } : {})}
      />
    </>
  );
}
