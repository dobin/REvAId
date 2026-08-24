/**
 * Minimal read-only detail panel (I6, pulled forward from I10's full
 * `DetailPanel`). Shows identity/address/kind/signature/fan counts for the
 * currently selected function — no rename, notes, long summary, or actions
 * (`InlineRename`, `NotesEditor`, `Regenerate`, colour/utility controls all
 * stay I10).
 */
import { useFunctionQuery } from "@/api/queries/functions";
import { useSummaryDemand } from "@/hooks/useSummaryDemand";
import { toHex } from "@/lib/hex";
import { useAppStore } from "@/store";

export function DetailPanel() {
  const selectedFunctionId = useAppStore((s) => s.selectedFunctionId);
  const { data: fn, isPending, isError } = useFunctionQuery(selectedFunctionId);

  // I9: the detail panel is another priority-0 surface for the selected
  // function's own summary — shares the same function id (and therefore
  // refcount) as the corresponding FunctionCardNode's `card:<id>` demand,
  // but is tracked under its own surface id so closing the panel alone
  // doesn't release a still-visible card's demand.
  useSummaryDemand({
    surface: `detail:${String(selectedFunctionId ?? "none")}`,
    functionIds: selectedFunctionId === null ? [] : [selectedFunctionId],
    priority: 0,
    enabled: selectedFunctionId !== null,
  });

  if (selectedFunctionId === null) return null;

  return (
    <aside
      style={{ width: "18rem", padding: "1rem", borderLeft: "1px solid #e5e7eb" }}
      aria-label="Function detail"
    >
      {isPending && <p>Loading…</p>}
      {isError && <p>Could not load function.</p>}
      {fn && (
        <div>
          <h2 className="gr-ground-truth" style={{ fontSize: "1rem", marginTop: 0 }}>
            {fn.displayName}
          </h2>
          <dl style={{ fontSize: "0.8125rem" }}>
            <dt style={{ color: "#6b7280" }}>Address</dt>
            <dd className="gr-ground-truth">{toHex(fn.address)}</dd>
            <dt style={{ color: "#6b7280" }}>Kind</dt>
            <dd>{fn.kind}</dd>
            {fn.signature && (
              <>
                <dt style={{ color: "#6b7280" }}>Signature</dt>
                <dd className="gr-ground-truth">{fn.signature}</dd>
              </>
            )}
            <dt style={{ color: "#6b7280" }}>Callers / Callees</dt>
            <dd>
              {fn.callerCount} / {fn.calleeCount}
            </dd>
          </dl>
        </div>
      )}
    </aside>
  );
}
