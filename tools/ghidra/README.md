# GraphRev Ghidra export

`GraphRevExport.java` is a [Ghidra](https://ghidra-sre.org/) script that exports
every function of the currently-open program to a single JSON file shaped for
GraphRev ingestion.

Ghidra has no built-in export that carries decompiled C, assembly, parameters,
and the call graph together, so this script produces exactly the fields the
GraphRev backend consumes. The output maps 1:1 onto the ingestion DTOs in
`backend/src/graphrev/adapters/ghidra/base.py` (`RawBinary`, `RawFunction`,
`RawParam`, `RawEdge`, `FunctionKind`), so a future file/REST `GhidraAdapter`
(Increment I12) can load it with no contract change.

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
  - **No** produces a complete export, including decompiled C where Ghidra
    can generate it.
  - **Yes** produces a faster export without decompilation. It still includes
    assembly, signatures, parameters, call edges, and resolved external
    imports; every `codeC` field is `null`.

### Headless (`analyzeHeadless`)

Run against an already-imported program in a Ghidra project:

```bash
$GHIDRA_HOME/support/analyzeHeadless \
    /path/to/project_dir ProjectName \
    -process acme.exe \
    -scriptPath /home/dobin/repos/Revealm/tools/ghidra \
    -postScript GraphRevExport.java /out/acme.json \
    -noanalysis
```

Or import + analyze + export in one shot:

```bash
$GHIDRA_HOME/support/analyzeHeadless \
    /path/to/project_dir ProjectName \
    -import /path/to/acme.exe \
    -scriptPath /home/dobin/repos/Revealm/tools/ghidra \
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

## Output schema (v1)

```jsonc
{
  "schemaVersion": 1,
  "binary": {
    "name": "acme.exe",
    "version": "",              // free text; overridable via arg 2
    "sourcePath": "/path/to/acme.exe",   // may be null
    "sha256": "…",              // may be null
    "functionCount": 182,
    "edgeCount": 431
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
      "calleeModule": null       // library name for an external callee; used if no target row exists
    }
  ]
}
```

### Field notes

- **Addresses are integers** (the function entry-point offset). The UI renders
  them as hex; storage is integer (`AS7`).
- **`kind` is never `placeholder`.** Placeholder rows are materialised by the
  ingestion pipeline (`B17`) from edges whose `calleeModule` is set and whose
  target is not a real function in the binary — the exporter only reports the
  four observable kinds.
- **Resolved imports are exported as functions.** The exporter walks Ghidra's
  external-location registry as well as the ordinary listing, so imports such
  as `ADVAPI32.DLL::EventRegister` are included with `kind: "external"`, no
  body/decompilation, and a library-qualified name. Calls through a local
  import thunk are emitted to that resolved external target.
- **`assembly` / `codeC` are `null`** for functions with no body
  (`import` / `thunk` / `external`), matching `RawFunction`.
- **Edges are de-duplicated** to one row per unique `(callerAddress,
  calleeAddress)` pair (multiple call sites collapse to one edge, per `D30`).
  Self-edges are kept for recursion.
- **`calleeModule`** is set when the callee is external or a thunk to an
  external. The exporter normally includes that resolved external function,
  so its edge resolves to the real `kind='external'` row. If a target is absent
  (for example, an unresolved cross-module edge), ingestion instead creates a
  `kind='placeholder'` function so the call stays visible without violating
  edge foreign keys.
- A decompilation error or timeout yields `codeC: null` and a warning on
  Ghidra's console; the export never aborts (mirrors ingestion rule `A4`).

## Verifying an export

```bash
jq . acme.json > /dev/null && echo "valid JSON"          # parses
jq '.functions | length' acme.json                        # function count
jq '.binary.functionCount' acme.json                      # should match
jq '.functions[] | select(.kind=="normal") | .codeC' acme.json | head   # spot-check C
jq '[.edges[] | {c:.callerAddress, e:.calleeAddress}] | unique | length' acme.json  # no dupes
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
