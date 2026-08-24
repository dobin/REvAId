/**
 * TESTING affordance: wipes every LLM summary (`summary_short`/
 * `summary_long` plus status/model metadata) for all functions of the
 * currently selected binary via `DELETE /binaries/{id}/summaries`.
 *
 * Useful for re-testing the summarisation pipeline end-to-end without
 * re-importing the binary. In-flight generations are not interrupted —
 * the worker may re-write one summary after the wipe.
 */
import { useClearBinarySummariesMutation } from "@/api/queries/summaries";
import type { BinaryId } from "@/api/types";

export function ResetSummariesButton({ binaryId }: { binaryId: BinaryId }) {
  const clearSummaries = useClearBinarySummariesMutation();

  return (
    <button
      type="button"
      disabled={clearSummaries.isPending}
      onClick={() => {
        clearSummaries.mutate(binaryId);
      }}
      style={{
        display: "block",
        padding: "0.125rem 0",
        marginBottom: "0.25rem",
        fontSize: "0.8125rem",
        textAlign: "left",
        background: "none",
        border: "none",
        cursor: clearSummaries.isPending ? "wait" : "pointer",
      }}
      title="Remove all LLM summaries from this binary (testing)"
    >
      {clearSummaries.isPending ? "Clearing…" : "✕ Reset summaries"}
    </button>
  );
}
