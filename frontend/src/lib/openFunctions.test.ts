import { describe, expect, it } from "vitest";
import { parseOpenFunctionsSearch, splitFunctionAddresses } from "./openFunctions";

describe("open-functions input", () => {
  it("splits pasted addresses on whitespace and commas", () => {
    expect(splitFunctionAddresses("0x1000, 0x2000\n4096\t0x3000")).toEqual([
      "0x1000",
      "0x2000",
      "4096",
      "0x3000",
    ]);
  });

  it("parses an encoded JSON query payload", () => {
    const payload = encodeURIComponent(JSON.stringify({
      addresses: ["0x180001000", "6442455040"],
      dllBase: "0x180000000",
    }));
    expect(parseOpenFunctionsSearch(`?open_functions=${payload}`)).toEqual({
      addresses: ["0x180001000", "6442455040"],
      dllBase: "0x180000000",
    });
  });

  it("rejects malformed JSON and invalid address schema", () => {
    expect(() => parseOpenFunctionsSearch("?open_functions=%7Bbad")).toThrow(
      "open_functions is not valid JSON.",
    );
    const invalid = encodeURIComponent(JSON.stringify({ addresses: ["nope"], dllBase: "0" }));
    expect(() => parseOpenFunctionsSearch(`?open_functions=${invalid}`)).toThrow(
      "Every function address",
    );
  });

  it("does not interpret fragment-only input", () => {
    expect(parseOpenFunctionsSearch("")).toBeNull();
  });
});
