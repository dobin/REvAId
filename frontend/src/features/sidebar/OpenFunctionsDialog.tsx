import { useEffect, useRef, useState } from "react";
import type {
  OpenFunctionsRequest,
  OpenFunctionsResponseDto,
  ViewId,
} from "@/api/types";
import { useOpenFunctionsMutation } from "@/api/queries/viewNodes";
import { Dialog } from "@/components/Dialog";
import { useCanvasActionsFromRegistry } from "@/features/canvas/CanvasActions";
import {
  defaultDllLoadBase,
  splitFunctionAddresses,
  validateOpenFunctionsRequest,
} from "@/lib/openFunctions";

const actionButtonStyle: React.CSSProperties = {
  display: "block",
  padding: "0.125rem 0",
  marginBottom: "0.25rem",
  fontSize: "0.8125rem",
  textAlign: "left",
  background: "none",
  border: "none",
  cursor: "pointer",
};

const fieldStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "0.5rem",
  border: "1px solid #d1d5db",
  borderRadius: "0.375rem",
  fontFamily: "ui-monospace, monospace",
  fontSize: "0.8125rem",
};

export function OpenFunctionsDialog({
  viewId,
  binaryLoadBase,
  automaticRequest,
  automaticError,
  automaticKey,
}: {
  viewId: ViewId | null;
  binaryLoadBase: number | null;
  automaticRequest?: OpenFunctionsRequest | null;
  automaticError?: string | null;
  automaticKey?: string;
}) {
  const [open, setOpen] = useState(false);
  const [addressesText, setAddressesText] = useState(automaticRequest?.addresses.join("\n") ?? "");
  const [dllBase, setDllBase] = useState(
    automaticRequest?.dllBase ?? defaultDllLoadBase(binaryLoadBase),
  );
  const [validationError, setValidationError] = useState<string | null>(automaticError ?? null);
  const [report, setReport] = useState<OpenFunctionsResponseDto | null>(null);
  const [focusId, setFocusId] = useState<number | null>(null);
  const consumedKey = useRef<string | null>(null);
  const mutation = useOpenFunctionsMutation(viewId ?? 0);
  const canvasActions = useCanvasActionsFromRegistry();

  const runImport = (request: OpenFunctionsRequest, automatic: boolean) => {
    if (viewId === null) return;
    setValidationError(null);
    setReport(null);
    mutation.mutate(request, {
      onSuccess: (response) => {
        setReport(response);
        setFocusId(response.rootFunctionId);
        if (!automatic || response.results.some((result) => result.status !== "resolved")) {
          setOpen(true);
        }
      },
      onError: (error) => {
        setValidationError(error instanceof Error ? error.message : "Could not open functions.");
        setOpen(true);
      },
    });
  };

  useEffect(() => {
    if (viewId === null || !automaticKey || consumedKey.current === automaticKey) return;
    consumedKey.current = automaticKey;
    if (automaticError) {
      setValidationError(automaticError);
      setOpen(true);
      return;
    }
    if (automaticRequest) {
      setAddressesText(automaticRequest.addresses.join("\n"));
      setDllBase(automaticRequest.dllBase);
      runImport(automaticRequest, true);
    }
    // The URL payload is intentionally consumed once for this mounted workspace.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewId, automaticKey, automaticRequest, automaticError]);

  useEffect(() => {
    if (focusId === null || canvasActions === null) return;
    canvasActions.focusFunction(focusId);
    setFocusId(null);
  }, [focusId, canvasActions, report]);

  const submit = () => {
    try {
      const request = validateOpenFunctionsRequest({
        addresses: splitFunctionAddresses(addressesText),
        dllBase,
      });
      runImport(request, false);
    } catch (error) {
      setValidationError(error instanceof Error ? error.message : "Invalid input.");
    }
  };

  const errorMessage = validationError ?? (mutation.error instanceof Error ? mutation.error.message : null);

  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      title="Open functions by address"
      trigger={
        <button type="button" style={actionButtonStyle} disabled={viewId === null}>
          <span aria-hidden="true">⊞</span> Open functions
        </button>
      }
    >
      <p style={{ margin: "0 0 0.75rem", color: "#6b7280", fontSize: "0.8125rem" }}>
        Paste runtime addresses. They are translated from the DLL load base into this binary’s analysis address space.
      </p>
      <label style={{ display: "block", marginBottom: "0.75rem", fontSize: "0.8125rem" }}>
        DLL load base
        <input
          aria-label="DLL load base"
          value={dllBase}
          onChange={(event) => {
            setDllBase(event.target.value);
          }}
          placeholder="0x180000000"
          style={{ ...fieldStyle, marginTop: "0.25rem" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: "0.75rem", fontSize: "0.8125rem" }}>
        Function addresses
        <textarea
          aria-label="Function addresses"
          value={addressesText}
          onChange={(event) => {
            setAddressesText(event.target.value);
          }}
          placeholder={"0x180001000\n0x180002340"}
          rows={8}
          style={{ ...fieldStyle, marginTop: "0.25rem", resize: "vertical" }}
        />
      </label>
      {errorMessage ? <p role="alert" style={{ color: "#b91c1c", fontSize: "0.8125rem" }}>{errorMessage}</p> : null}
      {report ? (
        <ul aria-label="Open function results" style={{ paddingLeft: "1.25rem", fontSize: "0.8125rem" }}>
          {report.results.map((result, index) => (
            <li key={`${result.inputAddress}-${String(index)}`}>
              <code>{result.inputAddress}</code>: {result.status}
              {result.displayName ? ` — ${result.displayName}` : ""}
              {result.message ? ` (${result.message})` : ""}
            </li>
          ))}
        </ul>
      ) : null}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
        <button type="button" onClick={submit} disabled={mutation.isPending || viewId === null}>
          {mutation.isPending ? "Opening…" : "Open functions"}
        </button>
      </div>
    </Dialog>
  );
}
