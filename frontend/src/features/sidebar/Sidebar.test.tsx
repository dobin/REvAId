import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  it("renders the legend heading", () => {
    render(<Sidebar />);
    expect(screen.getByText("Legend")).toBeInTheDocument();
  });
});
