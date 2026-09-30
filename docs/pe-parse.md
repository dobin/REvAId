# PE data-reference extraction

When a raw PE is imported through the decompile workflow, REvAId runs a best-effort enrichment step after importing the analysis export. It parses the original PE and scans each function's exported assembly for hexadecimal address literals. Literals that map to non-executable PE sections are treated as candidate data references; code addresses and values outside the image are ignored. This is static, literal-based extraction, not runtime tracing or full disassembly analysis.

For each distinct referenced location, REvAId records its PE section, RVA, writability, size, and a classification:

- **Import** — a normal or delay-load import slot, labeled with its DLL and symbol.
- **String / wide string** — printable ASCII or ASCII-range UTF-16LE text.
- **Pointer** — a pointer into the image; if it points to a recognized string, that text is included.
- **Bytes** — other initialized data, with a short hex preview.
- **Uninitialized** — a section location without file-backed bytes.

References retain the referring function, instruction address, and instruction text. Duplicate items and references are deduplicated during extraction. Results replace the binary's previous extracted items and references as one persistence operation; ordinary analysis-export imports do not run this PE enrichment step.

Extraction is enabled by default (`GRAPHREV_PE_DATA_ENABLED`). `GRAPHREV_PE_DATA_PREVIEW_BYTES` controls the byte preview (default 128), `GRAPHREV_PE_DATA_MAX_STRING_BYTES` limits stored string text (default 1024), and `GRAPHREV_PE_DATA_MAX_ITEMS` caps distinct extracted locations (default 200,000). Hitting the item cap produces a warning. PE parsing, extraction, and persistence failures are reported as warnings and do not undo the already imported analysis.
