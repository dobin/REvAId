import { describe, expect, it } from "vitest";
import { toHex } from "./hex";

describe("toHex", () => {
  it("formats an address as lowercase hex with a 0x prefix (AS7)", () => {
    expect(toHex(4198432)).toBe("0x401020");
  });

  it("formats zero", () => {
    expect(toHex(0)).toBe("0x0");
  });
});
