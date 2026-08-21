/**
 * Card-level summary area — same status machine as `SummaryCell` but at
 * card scale (no shimmer; I9 adds animation once the demand system exists).
 */
import type { FunctionDto } from "@/api/types";
import { SummaryCell } from "@/features/neighbours/SummaryCell";

export function CardSummary({ fn }: { fn: FunctionDto }) {
  return (
    <div style={{ padding: "0.5rem 0.75rem", fontSize: "0.8125rem", minHeight: "1.5rem" }}>
      <SummaryCell
        status={fn.summary.status}
        summaryShort={fn.summary.short}
        lowConfidence={fn.summary.lowConfidence}
        errorCode={fn.summary.errorCode}
      />
    </div>
  );
}
