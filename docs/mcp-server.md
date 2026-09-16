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

- `backend/src/graphrev/mcp/server.py` — MCP registration, Streamable HTTP startup, database session lifecycle, write locking, and error translation.
- `backend/src/graphrev/services/mcp_service.py` — binary/function resolution, validation, result assembly, and update orchestration.
- `backend/src/graphrev/schemas/mcp.py` — typed structured-output DTOs and ORM-to-output mapping.
- `backend/src/graphrev/repositories/functions.py` — exact function lookup, search including optional C content, and the allowlisted LLM-field update.
- `backend/src/graphrev/repositories/edges.py` — direct caller/callee queries and edge metadata.
- `backend/src/graphrev/core/config.py` — `mcp_host`, `mcp_port`, and search-limit settings.
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
- Full code bodies belong in `get_function`, not paginated search results.
- Headless graph queries must not depend on a UI `view_id`.

Possible future additions include bulk analysis writes, explicit field-clearing semantics, bounded or paginated relationship traversal, SSE/event integration through a shared transport, authentication for non-loopback deployment, and FTS indexing for large decompiled-code datasets.
