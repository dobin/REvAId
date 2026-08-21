/**
 * `OnCanvasList` (I6, deferred from I5 — "depends on `view_nodes`
 * persistence"). Lists this view's currently-visible nodes with a colour
 * swatch and pinned indicator; click focuses the node, and hidden nodes get
 * a "show" toggle to bring them back (D13's reversible hide).
 */
import { useViewQuery } from "@/api/queries/views";
import type { ViewId } from "@/api/types";
import { useCanvasActions } from "@/features/canvas/CanvasActions";
import { useViewNodeActions } from "@/features/canvas/useViewNodeActions";
import { useFunctionQuery } from "@/api/queries/functions";

export function OnCanvasList({ viewId }: { viewId: ViewId | null }) {
  const view = useViewQuery(viewId);
  const canvasActions = useCanvasActions();
  const nodeActions = useViewNodeActions(viewId ?? 0);

  if (viewId === null) return null;
  if (view.isPending) return <p>Loading…</p>;
  if (view.isError) return <p>Could not load view.</p>;

  const visible = view.data.nodes.filter((n) => n.visible);
  const hidden = view.data.nodes.filter((n) => !n.visible);

  return (
    <div>
      <h3 style={{ fontSize: "0.8125rem", fontWeight: 600 }}>On canvas</h3>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {visible.map((node) => (
          <OnCanvasRow
            key={node.functionId}
            functionId={node.functionId}
            pinned={node.pinned}
            onClick={() => {
              canvasActions?.focusFunction(node.functionId);
            }}
          />
        ))}
      </ul>
      {hidden.length > 0 && (
        <>
          <h3 style={{ fontSize: "0.8125rem", fontWeight: 600 }}>Hidden</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {hidden.map((node) => (
              <li key={node.functionId} style={{ display: "flex", gap: "0.375rem" }}>
                <HiddenLabel functionId={node.functionId} />
                <button
                  type="button"
                  onClick={() => {
                    nodeActions.setVisible(node.functionId, true);
                  }}
                >
                  Show
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function OnCanvasRow({
  functionId,
  pinned,
  onClick,
}: {
  functionId: number;
  pinned: boolean;
  onClick: () => void;
}) {
  const { data: fn } = useFunctionQuery(functionId);
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.375rem",
          background: "none",
          border: "none",
          cursor: "pointer",
          fontSize: "0.8125rem",
          padding: "0.125rem 0",
        }}
      >
        {pinned && <span aria-label="pinned">📌</span>}
        <span className="gr-ground-truth">{fn?.displayName ?? `#${String(functionId)}`}</span>
      </button>
    </li>
  );
}

function HiddenLabel({ functionId }: { functionId: number }) {
  const { data: fn } = useFunctionQuery(functionId);
  return (
    <span className="gr-ground-truth" style={{ fontSize: "0.8125rem" }}>
      {fn?.displayName ?? `#${String(functionId)}`}
    </span>
  );
}
