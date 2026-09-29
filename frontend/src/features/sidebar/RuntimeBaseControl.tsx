import { useState } from "react";
import { parseAddressNumber } from "@/lib/address";
import { toHex } from "@/lib/hex";

const inputStyle: React.CSSProperties = {
  width: "100%",
  fontSize: "0.8125rem",
  padding: "0.25rem 0.5rem",
  borderRadius: "0.375rem",
  border: "1px solid #d1d5db",
  boxSizing: "border-box",
};

export function RuntimeBaseControl({
  analysisImageBase,
  runtimeBase,
  onRuntimeBaseChange,
}: {
  analysisImageBase: number | null;
  runtimeBase: number | null;
  onRuntimeBaseChange: (value: number | null) => void;
}) {
  const [text, setText] = useState(
    runtimeBase === null
      ? analysisImageBase === null
        ? ""
        : toHex(analysisImageBase)
      : toHex(runtimeBase),
  );
  const parsed = parseAddressNumber(text);
  const invalid = text.trim().length > 0 && parsed === null;

  return (
    <div style={{ width: "12rem", flex: "0 0 auto" }}>
      <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: 600 }}>
        Image base
        <input
          type="text"
          aria-label="Runtime load base"
          placeholder="(optional)"
          value={text}
          onChange={(event) => {
            const next = event.target.value;
            setText(next);
            const nextBase = parseAddressNumber(next);
            if (next.trim().length === 0 || nextBase !== null) {
              onRuntimeBaseChange(nextBase);
            }
          }}
          style={{
            ...inputStyle,
            display: "block",
            marginTop: "0.35rem",
            padding: "0.55rem 0.65rem",
            fontSize: "0.9rem",
            fontWeight: 400,
            borderColor: invalid ? "#dc2626" : "#cbd5e1",
          }}
        />
      </label>
      {invalid ? (
        <p role="alert" style={{ fontSize: "0.75rem", color: "#b91c1c", margin: "0.25rem 0 0" }}>
          Enter a decimal or 0x-prefixed hexadecimal load base.
        </p>
      ) : null}
    </div>
  );
}