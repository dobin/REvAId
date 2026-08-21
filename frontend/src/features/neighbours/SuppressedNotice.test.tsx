import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SuppressedNotice } from "./SuppressedNotice";

describe("SuppressedNotice", () => {
  it("shows the caller count and a disabled 'Show anyway' button", () => {
    render(<SuppressedNotice total={291} />);
    expect(screen.getByText(/called by 291/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show anyway" })).toBeDisabled();
  });
});
