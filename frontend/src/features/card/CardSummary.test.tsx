import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CardSummary } from "./CardSummary";
import type { FunctionDto } from "@/api/types";

const baseFn: FunctionDto = {
  id: 1,
  binaryId: 1,
  address: 0x401000,
  displayName: "main",
  nameGhidra: "main",
  nameAnalyst: null,
  isRenamed: false,
  parameters: [],
  signature: null,
  kind: "normal",
  placeholderModule: null,
  fanIn: 0,
  fanOut: 16,
  isUtility: false,
  utilitySource: "computed",
  utilityOverride: null,
  summary: {
    status: "none",
    short: null,
    long: null,
    model: null,
    errorCode: null,
    lowConfidence: false,
    generatedAt: null,
    isStale: false,
  },
  notes: "",
  hasNotes: false,
  notesUpdatedAt: null,
  calleeCount: 16,
  callerCount: 0,
  hasIndirectCalls: false,
};

describe("CardSummary", () => {
  it("renders a dash when no summary exists yet", () => {
    render(<CardSummary fn={baseFn} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders the short summary when ready", () => {
    render(
      <CardSummary
        fn={{ ...baseFn, summary: { ...baseFn.summary, status: "ready", short: "Entry point." } }}
      />,
    );
    expect(screen.getByText(/entry point/i)).toBeInTheDocument();
  });
});
