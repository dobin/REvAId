import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SummaryCell } from "./SummaryCell";

describe("SummaryCell", () => {
  it("renders a dash for status=none", () => {
    render(<SummaryCell status="none" summaryShort={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders generating text for status=pending", () => {
    render(<SummaryCell status="pending" summaryShort={null} />);
    expect(screen.getByText(/generating/i)).toBeInTheDocument();
  });

  it("renders the short summary for status=ready", () => {
    render(<SummaryCell status="ready" summaryShort="Parses the header." />);
    expect(screen.getByText(/parses the header/i)).toBeInTheDocument();
  });

  it("marks low-confidence summaries", () => {
    render(<SummaryCell status="ready" summaryShort="Name-only." lowConfidence />);
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument();
  });

  it("marks stale summaries", () => {
    render(<SummaryCell status="stale" summaryShort="Old summary." />);
    expect(screen.getByText(/stale/i)).toBeInTheDocument();
  });

  it("renders the error code for status=error", () => {
    render(<SummaryCell status="error" summaryShort={null} errorCode="SUMMARY_PROVIDER_ERROR" />);
    expect(screen.getByText("SUMMARY_PROVIDER_ERROR")).toBeInTheDocument();
  });
});
