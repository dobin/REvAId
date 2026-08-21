import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CanvasEmptyState } from "./CanvasEmptyState";

describe("CanvasEmptyState", () => {
  it("renders the given message", () => {
    render(<CanvasEmptyState message="Pick a binary to get started." />);
    expect(screen.getByText("Nothing on the canvas yet")).toBeInTheDocument();
    expect(screen.getByText("Pick a binary to get started.")).toBeInTheDocument();
  });
});
