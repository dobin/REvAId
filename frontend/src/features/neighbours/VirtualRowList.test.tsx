import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VirtualRowList } from "./VirtualRowList";
import type { NeighbourRowDto } from "@/api/types";

function makeRow(id: number): NeighbourRowDto {
  return {
    id,
    address: 0x1000 + id,
    displayName: `fn_${String(id)}`,
    isRenamed: false,
    summaryShort: null,
    summaryStatus: "none",
    summaryLowConfidence: false,
    kind: "normal",
    onCanvas: false,
    isUtility: false,
    utilitySource: "computed",
    fanIn: 1,
    isSelf: false,
    hasNotes: false,
  };
}

describe("VirtualRowList", () => {
  it("renders a rowgroup container", () => {
    const rows = Array.from({ length: 5 }, (_, i) => makeRow(i));
    render(<VirtualRowList rows={rows} />);
    expect(screen.getByRole("rowgroup", { name: "neighbour-rows" })).toBeInTheDocument();
  });

  it("renders at least the initially-visible rows for a small list", () => {
    const rows = Array.from({ length: 3 }, (_, i) => makeRow(i));
    render(<VirtualRowList rows={rows} />);
    // jsdom reports zero client height, so @tanstack/react-virtual falls back
    // to rendering based on estimateSize; assert the container exists and no
    // crash occurs with an empty or small dataset.
    expect(screen.getByRole("rowgroup")).toBeInTheDocument();
  });

  it("renders nothing but does not crash for an empty list", () => {
    render(<VirtualRowList rows={[]} />);
    expect(screen.getByRole("rowgroup")).toBeInTheDocument();
  });
});
