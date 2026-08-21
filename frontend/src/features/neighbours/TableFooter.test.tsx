import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TableFooter } from "./TableFooter";

describe("TableFooter", () => {
  it("shows the shown/total counts and a disabled 'Fan out all' button", () => {
    render(<TableFooter shown={16} total={34} />);
    expect(screen.getByText("showing 16 of 34")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fan out all" })).toBeDisabled();
  });
});
