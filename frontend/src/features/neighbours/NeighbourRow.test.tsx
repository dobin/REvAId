import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NeighbourRow } from "./NeighbourRow";
import {
  CanvasActionsProvider,
  type CanvasActions,
  type FanOutOrigin,
} from "@/features/canvas/CanvasActions";
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
  it("renders address and name", () => {
    render(<NeighbourRow row={baseRow} />);
    expect(screen.getByText("0x401020")).toBeInTheDocument();
    expect(screen.getByText("open_file")).toBeInTheDocument();
  });

  it("shows the recursion glyph for self-calls and disables fan-out", () => {
    render(<NeighbourRow row={{ ...baseRow, isSelf: true }} />);
    expect(screen.getByRole("button", { name: "fan-out-or-focus" })).toBeDisabled();
  });

  it("shows the hide glyph when already placed", () => {
    render(<NeighbourRow row={{ ...baseRow, onCanvas: true }} />);
    expect(screen.getByRole("img", { name: /^hide$/i })).toBeInTheDocument();
  });

  function makeActions(): CanvasActions {
    return {
      fanOutFunction: vi.fn(),
      focusFunction: vi.fn(),
      hideFunction: vi.fn(),
    };
  }

  function renderWithActions(
    row: NeighbourRowDto,
    origin: FanOutOrigin | undefined,
    actions: CanvasActions,
  ) {
    return render(
      <CanvasActionsProvider value={actions}>
        <NeighbourRow row={row} origin={origin} />
      </CanvasActionsProvider>,
    );
  }

  it("fans out a caller row with the callers direction so it grows left", () => {
    const actions = makeActions();
    const origin: FanOutOrigin = { functionId: 1, direction: "callers" };
    renderWithActions(baseRow, origin, actions);
    screen.getByRole("button", { name: "fan-out-or-focus" }).click();
    expect(actions.fanOutFunction).toHaveBeenCalledWith(origin, baseRow.id);
  });

  it("disables the fan-out button when a placeable row has no origin", () => {
    // The original caller-fan-out bug: an enabled button that silently does
    // nothing. A row that isn't on-canvas and has no origin must be disabled.
    renderWithActions(baseRow, undefined, makeActions());
    expect(screen.getByRole("button", { name: "fan-out-or-focus" })).toBeDisabled();
  });
});
