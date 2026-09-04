# GraphRev Ghidra export

`GraphRevExport.java` is a [Ghidra](https://ghidra-sre.org/) script that exports
every function of the currently-open program to a single JSON file shaped for
GraphRev ingestion. This document is also the implementation contract for
other decompilers, including Kuna: an exporter for another tool must emit the
same JSON wire format and preserve the semantic rules below.

Ghidra has no built-in export that carries decompiled C, assembly, parameters,
and the call graph together, so this script produces the complete wire
document GraphRev consumes. The authoritative validation schema is
`backend/src/graphrev/schemas/ingest.py`; it is converted into the adapter DTOs
in `backend/src/graphrev/adapters/ghidra/base.py`. The metadata fields
`sha256`, `functionCount`, and `edgeCount` are retained in the wire format for
users but are informational: GraphRev recomputes the actual imported counts.

> The script is zero-dependency: it emits JSON with a small hand-rolled writer
> rather than relying on a JSON library that may not be on Ghidra's classpath.

## Running it

### GUI (Script Manager)

1. Open the program in the CodeBrowser and let auto-analysis finish.
2. **Window → Script Manager**.
3. Click the **Manage Script Directories** (list) icon and add this
   `tools/ghidra` directory, then **Refresh**.
4. Find **GraphRevExport** under the `GraphRev` category and run it (green
   arrow).
5. Pick a destination file when prompted. If you cancel, it defaults to
  `~/<program>_graphrev.json`.
6. Choose the export mode:
  - **Full export (recommended)** includes decompiled C where Ghidra can
    generate it.
  - **Minimal export** omits decompiled C for a faster export. It still
    includes assembly, signatures, parameters, call edges, and resolved
    external imports; every `codeC` field is `null`.

### Headless (`analyzeHeadless`)

Run against an already-imported program in a Ghidra project:

```bash
$GHIDRA_HOME/support/analyzeHeadless \
    /path/to/project_dir ProjectName \
    -process acme.exe \
    -scriptPath /home/dobin/repos/graphrev/tools/ghidra \
    -postScript GraphRevExport.java /out/acme.json \
    -noanalysis
```

Or import + analyze + export in one shot:

```bash
$GHIDRA_HOME/support/analyzeHeadless \
    /path/to/project_dir ProjectName \
    -import /path/to/acme.exe \
    -scriptPath /home/dobin/repos/graphrev/tools/ghidra \
    -postScript GraphRevExport.java /out/acme.json
```

  Headless exports always use complete mode with decompiled C, because the
  interactive mode prompt is not available.

Script arguments (both optional, positional):

| # | Arg           | Default                        |
| - | ------------- | ------------------------------ |
| 1 | output path   | `~/<program>_graphrev.json`    |
| 2 | binary version | `""` (free text — PRD `AS11`) |

The exporter appends `.json` when the selected or supplied output path does
not already have that extension.

## Output contract (schema v2)

GraphRev currently accepts schema versions **1** and **2**. New exporters
must emit **schema v2**. Use JSON UTF-8, camelCase keys, and JSON numbers for
all addresses and ordinals (never hexadecimal strings). The top-level keys
`schemaVersion`, `binary`, `functions`, and `edges` are required. The example
is the canonical v2 shape that new exporters must produce; `parameters` may be
an empty array. The server parser retains defaults for some omitted legacy or
hand-authored fields, but relying on those defaults is not a compatible
exporter implementation.

```jsonc
{
  "schemaVersion": 2,
  "binary": {
    "name": "acme.exe",
    "version": "",              // free text; overridable via arg 2
    "sourcePath": "/path/to/acme.exe",   // may be null
    "analysisImageBase": 4194304, // Ghidra's static program image base
    "sha256": "…",              // may be null; informational only
    "functionCount": 182,        // informational only; must match functions.length
    "edgeCount": 431             // informational only; must match edges.length
  },
  "functions": [
    {
      "address": 4198400,        // entry point, integer (hex is a UI concern)
      "name": "parse_config",    // Ghidra name (name_ghidra)
      "parameters": [
        { "ordinal": 0, "name": "buf", "type": "char *" }
      ],
      "signature": "int parse_config(char * buf)",   // may be null
      "assembly": "004010a0  PUSH RBP\n004010a1  MOV RBP,RSP\n…",  // null for import/thunk/external
      "codeC": "int parse_config(char *buf) { … }",  // null when not decompilable
      "kind": "normal",          // normal | import | thunk | external
      "hasIndirectCalls": false, // computed/indirect call present in the body
      "isEntryPoint": false      // main/WinMain/DllMain/entry/_start
    }
  ],
  "edges": [
    {
      "callerAddress": 4198400,
      "calleeAddress": 4198688,
      "calleeModule": null,      // library name for an external callee; used if no target row exists
      "calleeOrder": 0           // zero-based order among this caller's distinct callees
    }
  ]
}
```

| Object | Canonical v2 fields | Nullable fields |
| --- | --- | --- |
| Top-level | `schemaVersion`, `binary`, `functions`, `edges` | none |
| `binary` | `name`, `version`, `sourcePath`, `analysisImageBase`, `sha256`, `functionCount`, `edgeCount` | `sourcePath`, `analysisImageBase`, `sha256` |
| Each function | `address`, `name`, `parameters`, `signature`, `assembly`, `codeC`, `kind`, `hasIndirectCalls`, `isEntryPoint` | `signature`, `assembly`, `codeC` |
| Each parameter | `ordinal`, `name`, `type` | none |
| Each edge | `callerAddress`, `calleeAddress`, `calleeModule`, `calleeOrder` | `calleeModule` |

For a normal loaded binary, `analysisImageBase` should be the numeric static
image base. Use `null` only if the source tool has no meaningful equivalent.
Use `null`, rather than an empty string or a fabricated value, for unavailable
nullable text fields.

### Required semantics and invariants

- **Addresses are integers** from Ghidra's normal program address space: static
  virtual addresses (not RVAs) for ordinary loaded-memory functions. The UI
  renders them as hex; storage is integer (`AS7`). A document must use one
  consistent static-address space. Function addresses must be unique. Do not
  substitute a file offset, RVA, or a runtime ASLR address.
- **`analysisImageBase`** is Ghidra's image base captured at export time. It
  lets GraphRev translate a debugger's ASLR runtime VA to the stored static VA:
  `staticVA = runtimeVA - runtimeLoadBase + analysisImageBase`. It is not a
  runtime process load base.
- **`kind` is never `placeholder`.** Placeholder rows are materialised by the
  ingestion pipeline (`B17`) from edges whose `calleeModule` is set and whose
  target is not a real function in the binary — the exporter only reports
  `normal`, `import`, `thunk`, or `external`. Do not invent a different kind.
- **Resolved imports are exported as functions.** The exporter walks Ghidra's
  external-location registry as well as the ordinary listing, so imports such
  as `ADVAPI32.DLL::EventRegister` are included with `kind: "external"`, no
  body/decompilation, and a library-qualified name. Calls through a local
  import thunk are emitted to that resolved external target.
- **`assembly` / `codeC` are `null`** for functions with no body
  (`import` / `thunk` / `external`). For body-bearing functions, either string
  may still be `null` when the decompiler cannot provide it; failure to
  decompile one function must not abort the export.
- **Names, signatures, and parameter types are tool-provided text.** Preserve
  them as strings rather than attempting to normalize C syntax. Parameter
  ordinals are zero-based integers and must identify parameters in declaration
  order. Use `[]` when no parameters are known.
- **Edges are de-duplicated** to one row per unique `(callerAddress,
  calleeAddress)` pair across the entire document (multiple call sites collapse
  to one edge, per `D30`). Self-edges are kept for recursion. Emit every
  resolved call relation the tool can identify, including direct calls and
  tail-call candidates when the tool can distinguish them. Indirect/computed
  calls cannot be expressed as edges; set `hasIndirectCalls` on the caller
  when such a call is detected.
- **`calleeOrder`** is a zero-based, contiguous ordinal per caller. The
  exporter first discovers direct call references (and outgoing jump
  tail-call candidates) by walking the caller's instructions in ascending
  address order; a callee called more than once keeps its first location.
  It then supplements that result with any callee reported only by Ghidra's
  `getCalledFunctions()` API. Those location-unknown fallback callees appear
  at the end, ordered by entry address. This is deterministic static memory
  order, **not** dynamic runtime execution order across branches or loops.
- **`calleeModule`** is set when the callee is external or a thunk to an
  external. The exporter normally includes that resolved external function,
  so its edge resolves to the real `kind='external'` row. If a target is absent
  (for example, an unresolved cross-module edge), ingestion instead creates a
  `kind='placeholder'` function so the call stays visible without violating
  edge foreign keys.
- **Function coverage.** Include every function the decompiler knows about,
  including external/imported functions where the tool exposes them. An edge
  endpoint absent from `functions` is allowed only as a best-effort unresolved
  target; `calleeModule` should then identify its module when known. GraphRev
  creates a placeholder for any missing endpoint, but a real known function
  must not be intentionally omitted.
- A decompilation error or timeout yields `codeC: null` and a warning on
  the tool's console/log; the export never aborts (mirrors ingestion rule
  `A4`).

### Schema-version compatibility

- **v2 (required for new exporters):** every edge has a non-negative integer
  `calleeOrder`; for each `callerAddress`, the values are distinct and exactly
  `0, 1, …, N-1`. A stable static first-call-site order is recommended. When
  source locations are unavailable, append affected callees in a deterministic
  order. It is not a runtime execution order.
- **v1 (legacy input only):** omits `calleeOrder`, and GraphRev stores the
  order as unknown. Do not emit v1 from Kuna or any new exporter.

## Verifying an export

```bash
jq . acme.json > /dev/null && echo "valid JSON"          # parses
jq '.functions | length' acme.json                        # function count
jq '.binary.functionCount' acme.json                      # should match
jq '.functions[] | select(.kind=="normal") | .codeC' acme.json | head   # spot-check C
jq '[.edges[] | {c:.callerAddress, e:.calleeAddress}] | unique | length' acme.json  # no dupes
jq '[.edges | sort_by(.callerAddress) | group_by(.callerAddress)[] | sort_by(.calleeOrder) | [.[] | .calleeOrder] == [range(0; length)]] | all' acme.json  # contiguous per-caller order
```

## Limitations / notes

- Decompilation is **serial** for readability and robustness. Very large
  binaries (tens of thousands of functions) will be slow; a parallel
  `ChunkingParallelDecompiler` variant is a future optimisation.
- The exporter prints aggregate `collect`, `export`, `write`, and `total`
  timings to Ghidra's console. In complete mode, the serial decompilation work
  is normally the largest part of the `export` time.
- `version` has no reliable source in Ghidra, so it defaults to `""`. Treat a
  rebuilt binary as a new binary (a new `binaries` row) rather than relying on
  this field.
- Loading the exported file into GraphRev is Increment **I12** and is not part
  of this tool — the exporter only produces the file.
- GraphRev accepts schema-v1 and schema-v2 exports. Schema v1 has no imported
  callee order; schema v2 preserves `edges[].calleeOrder` for ordered callee
  tables.
