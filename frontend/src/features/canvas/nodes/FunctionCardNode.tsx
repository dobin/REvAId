/**
 * React Flow custom node — the function card (TAD §2.3/§4.3). Composes
 * `CardHeader` + `CardSummary` + both `NeighbourTable`s. No `Handle`s: I5
 * renders exactly one node and no edges.
 */
import { useConfig } from "@/config/ConfigProvider";
import { useFunctionQuery } from "@/api/queries/functions";
import type { FunctionId, ViewId } from "@/api/types";
import { CardHeader } from "@/features/card/CardHeader";
import { CardSummary } from "@/features/card/CardSummary";
import { NeighbourTable } from "@/features/neighbours/NeighbourTable";

export interface FunctionCardNodeData {
  functionId: FunctionId;
  viewId: ViewId;
}

export function FunctionCardNode({ data }: { data: FunctionCardNodeData }) {
  const config = useConfig();
  const { data: fn, isPending, isError } = useFunctionQuery(data.functionId);

  return (
    <div
      style={{
        width: config.cardWidthPx,
        background: "white",
        border: "1px solid #d1d5db",
        borderRadius: "0.375rem",
        boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
      }}
    >
      {isPending && <p style={{ padding: "0.75rem" }}>Loading function…</p>}
      {isError && <p style={{ padding: "0.75rem" }}>Could not load function.</p>}
      {fn && (
        <>
          <CardHeader fn={fn} />
          <CardSummary fn={fn} />
          <div style={{ padding: "0 0.75rem 0.75rem" }}>
            <NeighbourTable functionId={data.functionId} viewId={data.viewId} direction="callees" />
            <NeighbourTable functionId={data.functionId} viewId={data.viewId} direction="callers" />
          </div>
        </>
      )}
    </div>
  );
}
