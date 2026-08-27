import { toHex } from "@/lib/hex";

const HEX_ADDRESS = /^0x[0-9a-f]+$/i;

export type AddressLookup =
  | { kind: "text" }
  | { kind: "invalid"; message: string }
  | { kind: "address"; canonicalAddress: number; displayAddress: string };

/** Parse the user-entered runtime-base field as decimal or prefixed hexadecimal. */
export function parseAddressNumber(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) return null;
  if (!/^(?:0x[0-9a-f]+|[0-9]+)$/i.test(trimmed)) return null;

  const parsed = Number(trimmed);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
}

/**
 * Interpret only `0x…` input as address lookup. A configured runtime base
 * translates the debugger VA into GraphRev's static Ghidra address space.
 */
export function resolveAddressLookup(
  input: string,
  runtimeBase: number | null,
  analysisImageBase: number | null,
): AddressLookup {
  const trimmed = input.trim();
  if (!trimmed.toLowerCase().startsWith("0x")) return { kind: "text" };
  if (!HEX_ADDRESS.test(trimmed)) return { kind: "invalid", message: "Enter a valid hexadecimal address." };

  const runtimeAddress = Number(trimmed);
  if (!Number.isSafeInteger(runtimeAddress)) {
    return { kind: "invalid", message: "Address exceeds JavaScript’s safe integer range." };
  }
  if (runtimeBase === null) {
    return {
      kind: "address",
      canonicalAddress: runtimeAddress,
      displayAddress: toHex(runtimeAddress),
    };
  }
  if (analysisImageBase === null) {
    return {
      kind: "invalid",
      message: "This binary has no recorded Ghidra image base. Re-export and re-ingest it to resolve runtime addresses.",
    };
  }

  const canonicalAddress = runtimeAddress - runtimeBase + analysisImageBase;
  if (!Number.isSafeInteger(canonicalAddress) || canonicalAddress < 0) {
    return { kind: "invalid", message: "Runtime address cannot be translated using this load base." };
  }
  return { kind: "address", canonicalAddress, displayAddress: toHex(canonicalAddress) };
}