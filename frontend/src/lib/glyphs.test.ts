import { describe, expect, it } from "vitest";
import { GLYPHS, M0_GLYPHS } from "./glyphs";

describe("glyphs", () => {
  it("uses the fan-out glyph U+2922, not the PRD's typo U+2932", () => {
    expect(GLYPHS.fanOut).toBe("\u2922");
  });

  it("every M0-scoped glyph key exists in GLYPHS", () => {
    for (const key of M0_GLYPHS) {
      expect(GLYPHS[key]).toBeDefined();
    }
  });
});
