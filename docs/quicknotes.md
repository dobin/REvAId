# Quick Notes

Bm_GetMetaStore

-----


Mid-function addresses: resolve_address
-> The find_functions should be able to handle it by finding the right one - if we have the size

Raw bytes: read_bytes
Opcode scan: search_bytes
Build identification: get_metadata


* get_imports, get_exports (from PE)
* Call-graph path: reaches / callgraph_path
* Match locations: search_code
  * doesnt always return all code (only matching lines)
  * find_functions already searches decompiled C but returns whole functions. Return matching lines and field names; callee filtering can use edges. String/type/allocator filters need careful semantics and possibly indexed xrefs.
* Batched reads: decompile_many
  * Resolve selectors and return stored C/assembly in one bounded request. No new decompilation is needed.

------------

Recommended first pass: fix name resolution; add get_metadata and the straightforward PE-header tools; add read_bytes, list_functions, match-location search_code, and decompile_many. 

Then implement bounded reaches. 

For the original mpengine question, prioritize exact-build verification and Ghidra-exported function extents and xrefs before promising that resolve_address or constructor queries are definitive.

One implementation caution: the existing resolve_function_by_address returns the nearest earlier start, not proven containment, and the schema stores only one kind per caller–callee edge (functions.py, models.py). Neither should silently be presented as instruction-accurate evidence.

------------------


For this workspace, I’d make PE extraction a separate enrichment step, keyed to the same binary using binary.sha256, and normalize PE RVAs to the export’s analysisImageBase before matching addresses. The current exporter already includes Ghidra-resolved external functions and library-qualified import names in GraphRevExport.java; avoid adding duplicate function rows or edges for them. Libraries such as LIEF or pefile would be reasonable choices for the PE-reading step; neither is currently a dependency in pyproject.toml.


Imports and delay-load imports	
Identify DLLs, names or ordinals, and IAT slots; enrich external-function labels.

Exports	
Mark exported functions and data, including names, ordinals, and forwarded exports.

PE/COFF symbols and optional PDB data	
Add names where available. A stripped PE may have few useful symbols without its PDB.

