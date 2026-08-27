import { describe, expect, it } from "vitest";
import { parseAddressNumber, resolveAddressLookup } from "./address";

describe("address parsing and resolution", () => {
  it("accepts decimal and hexadecimal runtime bases", () => {
    expect(parseAddressNumber("4194304")).toBe(0x400000);
    expect(parseAddressNumber("0x400000")).toBe(0x400000);
    expect(parseAddressNumber("nope")).toBeNull();
  });

  it("converts a runtime VA into the stored Ghidra static VA", () => {
    expect(resolveAddressLookup("0x7fff078112c4", 0x7ffeefb40000, 0x168d7b8cc)).toEqual({
      kind: "address",
      canonicalAddress: 0x180a4cb90,
      displayAddress: "0x180a4cb90",
    });
  });

  it("keeps ordinary text as a substring search", () => {
    expect(resolveAddressLookup("parse_config", null, null)).toEqual({ kind: "text" });
  });
});