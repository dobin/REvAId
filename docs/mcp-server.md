# GraphRev MCP server

GraphRev includes an agent-facing [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for querying and augmenting imported binary-analysis data.

The server uses Streamable HTTP and connects directly to the same SQLite database as the GraphRev API. It does not proxy requests through the REST API or communicate with Ghidra directly.

## Running the server

Migrate and populate the database first, then start the server:

```sh
just migrate
just mcp
```

The default MCP endpoint is:

```text
http://127.0.0.1:8001/mcp
```

The bind address and port can be changed with `GRAPHREV_MCP_HOST` and `GRAPHREV_MCP_PORT`. The default loopback binding should be retained unless authentication and TLS are supplied by a trusted reverse proxy.

The server is also installed as the `graphrev-mcp` console command.

## Binary and function identity

Every function tool requires `binary_name`. `binary_version` is optional and defaults to the empty string, but it is part of the binary's unique identity.

`get_function` and `set_function_info` require exactly one function selector:

- `function_id`: GraphRev database ID.
- `address`: exact function start address as an integer. MCP clients may send decimal or JSON integer values; returned data also includes `addressHex` for display.
- `name`: exact, case-insensitive match against `name`, `name_llm`, or `name_analyst`.

Names are not guaranteed to be unique. An ambiguous name returns candidate IDs and addresses; retry with `function_id` or `address`. IDs and addresses obtained from `find_functions` are therefore the preferred selectors.

## Tools

### `list_binaries`

Lists the binaries available in the configured database.

Each result contains:

- Binary name and version.
- Function count.
- Edge count.

Agents can use this tool before other calls to discover the exact binary identity.

### `find_functions`

Searches functions belonging to one binary. Parameters include `binary_name`, optional `binary_version`, optional `query`, `limit`, and `offset`.

The query is a case-insensitive substring search over:

- Ghidra, LLM, and analyst function names.
- Analyst notes.
- Decimal and hexadecimal address renderings.
- Decompiled C (`code_c`).

An omitted query lists functions using pagination. `limit` is clamped to `function_search_max_limit` (default 200).

Results intentionally contain summary metadata rather than full function bodies: ID, integer and hexadecimal address, names, signature, kind, short summary, and fan-in/fan-out. Use `get_function` for code and relationships.

### `search_code`

Greps the decompiled C of one binary (case-insensitive substring). Parameters: `binary_name`, `query`, optional `binary_version`, `context_lines` (default 3, max 20), `limit` (default 20, clamped like `find_functions`), and `offset`.

For each matching function it returns ID, address, name, signature, match count, and hunks of matching lines with surrounding context. Overlapping windows are merged; each line has its 1-based number and an `isMatch` flag. Use it to locate code before fetching whole functions.

### `decompile_many`

Returns decompiled C for up to 20 functions in one call. `functions` is a list of selectors (`function_id`, `address`, or `name`; exactly one each). Unknown or ambiguous selectors yield a per-entry `error` and do not fail the call.

### `get_function`

Returns the analysis context for one function:

- Address and all stored names.
- Parameters and signature.
- Assembly/disassembly.
- Decompiled C.
- Function kind and placeholder module.
- Entry-point and indirect-call indicators.
- Fan-in and fan-out.
- Current summary state.
- Direct callers and callees.

Related functions include their IDs, addresses, names, signatures, short summaries, and edge metadata. Callers are ordered by address. Callees are ordered by imported static call order when available, followed by address. `hasIndirectCalls=true` means the returned callee set may be incomplete.

### `set_function_info`

Partially updates information produced by an analysis agent. It accepts one function selector and one or more of:

- `name_llm`
- `summary_short`
- `summary_long`

Only supplied, non-null fields are changed; other values are retained. A successful update sets `summary_status` to `ready` and updates the function timestamp.

This tool cannot modify ingestion-owned ground truth (`assembly`, `code_c`, addresses, edges, or Ghidra names) or analyst-owned fields. Values cannot currently be cleared through this tool because `null` means “not supplied.”

MCP writes are committed directly to SQLite. Since the MCP server is a separate process, writes do not publish events through the API's in-process SSE bus; clients see them on their next read or refresh.

## Data items (strings, imports, globals)

When a binary is imported from a **raw PE** (API `POST /api/v1/binaries/decompile` or `graphrev decompile`), the stored assembly of every function is scanned for literal addresses. Addresses that fall in a non-executable PE section (`.data`, `.rdata`, `.idata`, ...) become *data items* (classified with `pefile` as `string`, `wstring`, `pointer`, `import`, `bytes` or `uninitialized`), and each referencing instruction becomes a *data reference* from the function to the item, similar to the call graph.

Limits to keep in mind:

- JSON-only imports have no data items (the PE is not available).
- References are parsed from assembly text. Computed or indirect addresses (`[RBX + 0x30]`, table lookups) are **not** found, so absence of a reference is not proof.
- Only referenced locations are indexed; the PE is not scanned for unreferenced strings.
- Extraction is best-effort: if it fails the import still succeeds and the result carries a warning (`warnings`, plus `dataItemsInserted` / `dataRefsInserted`).
- The PE is not kept after import, so the data can only be rebuilt by re-importing.

All data tools take `binary_name` and optional `binary_version`, and paginate with `limit`/`offset` (clamped to the function-search maximum).

### `search_data`

Searches a binary's data items. `query` is a case-insensitive substring of the decoded value (string text, import `DLL::Name`, pointed-to string), of the address (hex or decimal), or a hex byte sequence (`de ad be ef`, `0xdeadbeef`, `\xde\xad`) matched against the stored bytes. Strings are stored up to 1024 bytes and raw data (`bytes`, `pointer`) up to the first 128 bytes, both cut off (`pe_data_max_string_bytes`, `pe_data_preview_bytes`); matches beyond the cut-off are not found. A short hex-looking query such as `add` can also match byte previews; use `kind` to narrow. Filters: `kind`, `section`, `min_refs`, `max_refs`. `sort` is `address`, `refs_asc` (rarest first) or `refs_desc`. Items report address, RVA, section, kind, size, value, pointer target, a hex preview, writability and `refCount`.

### `get_data_item`

Returns one item (by `data_item_id` or `address`) and every referencing function and instruction, including the assembly line.

### `get_function_data`

Lists the data items one function references (selector: `function_id`, `address`, or `name`), in instruction order.

### `find_functions_by_data`

Same filters as `search_data`, but returns the *functions* that reference matching items, each once with its matching items. Use it for questions like "which functions use a string containing `password`" or "which import `CreateRemoteThread`".

### `find_related_functions`

Ranks other functions by data items shared with a given function. Items referenced by more than `max_item_ref_count` instructions (default 20; e.g. the security cookie) are ignored, and rarer items weigh more (score $\sum 1/\text{refCount}$). The shared items are returned as evidence.

## Errors

Application errors are converted into MCP `ToolError` responses with GraphRev's machine-readable code, message, and optional details. Common cases are:

- `BINARY_NOT_FOUND`: the name/version pair does not exist.
- `FUNCTION_NOT_FOUND`: the selector does not resolve within that binary.
- `VALIDATION_ERROR`: invalid pagination, multiple/no selectors, an ambiguous name, or no update fields.

## Implementation overview

The implementation follows the existing backend layering:

```text
MCP transport → service → repositories → SQLAlchemy models / SQLite
```

Important files:

- `backend/src/revaid_mcp/server.py` — MCP registration, Streamable HTTP startup, database session lifecycle, write locking, and error translation.
- `backend/src/revaid/services/mcp_service.py` — binary/function resolution, validation, result assembly, and update orchestration.
- `backend/src/revaid/schemas/mcp.py` — typed structured-output DTOs and ORM-to-output mapping.
- `backend/src/revaid/repositories/functions.py` — exact function lookup, search including optional C content, and the allowlisted LLM-field update.
- `backend/src/revaid/repositories/edges.py` — direct caller/callee queries and edge metadata.
- `backend/src/revaid/repositories/data_items.py` — data item/reference storage and search queries.
- `backend/src/revaid/ingestion/pe_data/` — assembly literal parsing, `pefile` wrapper, classification and post-import enrichment.
- `backend/src/revaid_contracts/config.py` — `mcp_host`, `mcp_port`, search-limit and `pe_data_*` settings.
- `backend/tests/services/test_mcp_service.py` and `backend/tests/repositories/test_functions_read.py` — service and search behavior.

`MCPServer` derives each tool's input and structured-output schema from its Python type annotations. DTOs inherit GraphRev's `ApiModel`, so serialized field names use camelCase.

The MCP process constructs its own async SQLAlchemy engine and session factory. Reads use request-local sessions. Writes additionally acquire GraphRev's process-local `write_lock`; cross-process contention with the API or ingestion CLI is handled by SQLite WAL and `busy_timeout`.

## Extending the server

When adding a tool or field:

1. Add narrowly scoped database behavior to `repositories/` when a new query or mutation is required. Keep mutations explicitly allowlisted, especially around ingestion-, analyst-, and LLM-owned columns.
2. Add orchestration and GraphRev errors to `services/mcp_service.py`.
3. Add or extend a DTO and mapping function in `schemas/mcp.py`. Avoid returning raw ORM objects.
4. Register a thin typed tool in `mcp/server.py`. Convert `AppError` to `ToolError`; do not place SQL or business rules in the transport function.
5. Add focused repository/service tests. For transport changes, also verify `await mcp.list_tools()` and exercise the tool with an MCP client where practical.
6. Run backend tests, Ruff, mypy, and import-linter.

Preserve these current invariants:

- Every function operation is scoped to an explicit binary name/version.
- A function ID must belong to that binary.
- Function names may be ambiguous; never silently choose one.
- MCP writes must not overwrite ingestion-owned or analyst-owned data.
- Full code bodies belong in `get_function` and `decompile_many`, not paginated search results. `search_code` returns only matching snippets.
- Headless graph queries must not depend on a UI `view_id`.

Possible future additions include bulk analysis writes, explicit field-clearing semantics, bounded or paginated relationship traversal, SSE/event integration through a shared transport, authentication for non-loopback deployment, and FTS indexing for large decompiled-code datasets.
