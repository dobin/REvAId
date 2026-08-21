import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Glyph } from "./Glyph";

describe("Glyph", () => {
  it("renders the glyph character with an accessible label", () => {
    render(<Glyph name="fanOut" />);
    const el = screen.getByRole("img", { name: /fan out/i });
    expect(el).toHaveTextContent("⤢");
    expect(el).toHaveAttribute("title", expect.stringMatching(/fan out/i));
  });

  it("applies a custom className", () => {
    render(<Glyph name="utility" className="gr-glyph" />);
    expect(screen.getByRole("img", { name: /utility/i })).toHaveClass("gr-glyph");
  });
});
