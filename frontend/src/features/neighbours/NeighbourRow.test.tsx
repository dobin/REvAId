import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NeighbourRow } from "./NeighbourRow";
import type { NeighbourRowDto } from "@/api/types";

const baseRow: NeighbourRowDto = {
  id: 2,
  address: 4198432,
  displayName: "open_file",
  isRenamed: false,
  summaryShort: null,
  summaryStatus: "none",
  summaryLowConfidence: false,
  kind: "normal",
  onCanvas: false,
  isUtility: false,
  utilitySource: "computed",
  fanIn: 3,
  isSelf: false,
  hasNotes: false,
};

describe("NeighbourRow", () => {
  it("renders address, name, and summary", () => {
    render(<NeighbourRow row={baseRow} />);
    expect(screen.getByText("0x401020")).toBeInTheDocument();
    expect(screen.getByText("open_file")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows the recursion glyph for self-calls and disables fan-out", () => {
    render(<NeighbourRow row={{ ...baseRow, isSelf: true }} />);
    expect(screen.getByRole("button", { name: "fan-out-or-focus" })).toBeDisabled();
  });

  it("shows the on-canvas glyph when already placed", () => {
    render(<NeighbourRow row={{ ...baseRow, onCanvas: true }} />);
    expect(screen.getByRole("img", { name: /already on canvas/i })).toBeInTheDocument();
  });
});
