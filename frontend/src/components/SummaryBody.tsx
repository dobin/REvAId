/**
 * Shared presentation of an LLM summary's `short` + `long` text, used by both
 * the neighbour-row hover tooltip (`FunctionInfoTooltip`) and the card-level
 * click popover (`SummaryPopover` via `CardSummary`). Extracted so both
 * surfaces read identically: `summary_short` is set in semibold as its own
 * block (a scannable one-liner), `summary_long` follows below in normal weight
 * with `pre-wrap` so model-emitted paragraph breaks survive.
 *
 * Formatting only — no data fetching, no summary-demand side effects. Callers
 * pass the already-loaded summary fields. Renders a muted placeholder for the
 * empty/`none` case so neither surface has to special-case it.
 */
import type { SummaryStatus } from "@/api/types";

export function SummaryBody({
  status,
  short,
  long,
}: {
  status: SummaryStatus;
  short: string | null;
  long: string | null;
}) {
  if (status === "none" || (!short && !long)) {
    return <p style={{ margin: 0, color: "#9ca3af" }}>No summary yet.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {short && (
        <p style={{ margin: 0, fontWeight: 600 }}>
          {short}
          {status === "stale" && " (stale)"}
        </p>
      )}
      {long && <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{long}</p>}
    </div>
  );
}
