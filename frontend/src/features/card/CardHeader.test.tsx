import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CardHeader } from "./CardHeader";
import type { FunctionDto } from "@/api/types";

const baseFn: FunctionDto = {
  id: 1,
  binaryId: 1,
  address: 0x401000,
  displayName: "main",
  nameGhidra: "main",
  nameAnalyst: null,
    nameLlm: null,
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
    adapter: null,
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

describe("CardHeader", () => {
  it("renders the display name and hex address", () => {
    render(<CardHeader fn={baseFn} />);
    expect(screen.getByText("main")).toBeInTheDocument();
    expect(screen.getByText("0x401000")).toBeInTheDocument();
  });

  it("shows the renamed glyph when isRenamed", () => {
    render(<CardHeader fn={{ ...baseFn, isRenamed: true, displayName: "parse_config" }} />);
    expect(screen.getByRole("img", { name: /renamed/i })).toBeInTheDocument();
  });

  it("shows the has-notes glyph when hasNotes", () => {
    render(<CardHeader fn={{ ...baseFn, hasNotes: true }} />);
    expect(screen.getByRole("img", { name: /has analyst notes/i })).toBeInTheDocument();
  });
});
