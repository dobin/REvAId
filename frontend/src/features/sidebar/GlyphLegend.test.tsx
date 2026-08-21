import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GlyphLegend } from "./GlyphLegend";
import { M0_GLYPHS, GLYPH_LABELS } from "@/lib/glyphs";

describe("GlyphLegend", () => {
  it("renders a legend entry for every M0-scoped glyph", () => {
    render(<GlyphLegend />);
    for (const key of M0_GLYPHS) {
      expect(screen.getByText(GLYPH_LABELS[key])).toBeInTheDocument();
    }
  });
});
