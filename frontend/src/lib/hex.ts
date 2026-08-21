/**
 * Address formatting. AS7: addresses are stored as integers; hex is
 * display-only. This is the single place that formatting happens so every
 * card/table/detail-panel address renders identically.
 */

export function toHex(address: number): string {
  return `0x${address.toString(16)}`;
}
