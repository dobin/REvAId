import type { OpenFunctionsRequest } from "@/api/types";
import { toHex } from "@/lib/hex";

const ADDRESS = /^(?:0x[0-9a-f]+|[0-9]+)$/i;
export const DEFAULT_DLL_LOAD_BASE = 0x140000000;

export function defaultDllLoadBase(binaryBase: number | null): string {
  return toHex(binaryBase ?? DEFAULT_DLL_LOAD_BASE);
}

function isAddress(value: unknown): value is string {
  return typeof value === "string" && ADDRESS.test(value.trim());
}

export function splitFunctionAddresses(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((value) => value.trim())
    .filter(Boolean);
}

export function validateOpenFunctionsRequest(value: unknown): OpenFunctionsRequest {
  if (typeof value !== "object" || value === null) {
    throw new Error("open_functions must be a JSON object.");
  }
  const candidate = value as { addresses?: unknown; dllBase?: unknown };
  if (!Array.isArray(candidate.addresses) || candidate.addresses.length === 0) {
    throw new Error("open_functions.addresses must be a non-empty array.");
  }
  if (!candidate.addresses.every(isAddress)) {
    throw new Error("Every function address must be decimal or 0x-prefixed hexadecimal.");
  }
  if (!isAddress(candidate.dllBase)) {
    throw new Error("open_functions.dllBase must be decimal or 0x-prefixed hexadecimal.");
  }
  return {
    addresses: candidate.addresses.map((address) => address.trim()),
    dllBase: candidate.dllBase.trim(),
  };
}

export function parseOpenFunctionsSearch(search: string): OpenFunctionsRequest | null {
  const raw = new URLSearchParams(search).get("open_functions");
  if (raw === null) return null;
  try {
    return validateOpenFunctionsRequest(JSON.parse(raw));
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error("open_functions is not valid JSON.");
    }
    throw error;
  }
}