# JSON export structure

A binary-analysis export is a JSON object with four top-level fields:

- `schemaVersion` identifies the export format. This example uses version 2; the importer currently accepts versions 1, 2, and 4. Versions 2 and 4 require each edge to include a valid `calleeOrder`.
- `binary` contains metadata for the analyzed executable: `name`, optional `version` and `sourcePath`, optional `analysisImageBase` and `sha256`, and informational `functionCount` and `edgeCount` values.
- `functions` is an array of function or address records. Each record has an `address` and `name`; it can also include `parameters` (each with an `ordinal`, `name`, and `type`), `signature`, `assembly`, decompiled `codeC`, `kind`, `hasIndirectCalls`, and `isEntryPoint`. Fields without values may be omitted or null where allowed. Kuna schema v4 can also include non-executable `data` records.
- `edges` is an array of directed relationships between records. Each edge identifies a `callerAddress` and `calleeAddress`; it can specify a `kind` (such as `call`, `jump`, or `data`) and, when applicable, `calleeModule`. In versions 2 and 4, `calleeOrder` gives the zero-based order of distinct callees for that caller.

Addresses are numeric values. Function and edge references use those addresses to connect the graph; edges may refer to callees not listed in `functions`, for example when the target is in another module.
