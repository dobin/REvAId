# Binary import identity and duplicate handling

This document records the binary identity rules implemented as of 2026-09-07. It is intended as a reference for future import, decompiler, persistence, and UI changes.

## Core rules

1. A SHA-256 digest is the preferred identity for imported binary content.
2. If an import has no SHA-256 digest, duplicate detection falls back to the effective `(name, version)` pair.
3. SHA-256 values from JSON exports must contain exactly 64 hexadecimal characters. They are normalized to lowercase.
4. Raw executable uploads are hashed by GraphRev from the original uploaded bytes before decompilation. The computed digest is authoritative; metadata emitted by the decompiler cannot replace it.
5. The database retains the unique `(name, version)` constraint in addition to the hash lookup index.
6. `binaries.sha256` is nullable for legacy exports and non-file adapters.
7. The SHA-256 index is intentionally not unique because public mode permits repeated content under independently randomized names.

## Behavior matrix

| Mode | Source | Effective submitted name | Hash source | Duplicate behavior |
|---|---|---|---|---|
| Private | Raw executable | Raw upload `name` query parameter; the frontend normally uses the selected executable filename | GraphRev computes SHA-256 from uploaded bytes | Reject an existing hash. If no hash match exists, reject an existing `(name, version)` |
| Private | JSON export with hash | `binary.name` in the submitted JSON document | `binary.sha256` | Reject an existing hash, even if the incoming name differs. Otherwise reject an existing `(name, version)` |
| Private | JSON export without hash | `binary.name` in the submitted JSON document | None | Reject an existing `(name, version)` |
| Public | Raw executable | Submitted name is randomized in the backend before persistence | GraphRev computes SHA-256 from uploaded bytes | Identical content may create another row under a different randomized name; only a randomized `(name, version)` collision is rejected |
| Public | JSON export | `binary.name` is randomized in the backend before persistence | Optional `binary.sha256` | Identical content may create another row under a different randomized name; only a randomized `(name, version)` collision is rejected |

> **Current transport detail:** JSON uploads send the parsed JSON document, not the browser-selected `.json` filename. Therefore the effective JSON name currently comes from `binary.name`, rather than from the uploaded export file's filesystem name. Changing this requires extending the JSON upload protocol to carry the selected filename explicitly.

## Private mode

Private mode does not permit import-time overwrite or refresh through the import dialog.

Duplicate checks happen in this order:

1. If the incoming document has a hash, look for an existing row with that hash.
2. If no hash match is found, look for an existing row with the same `(name, version)`.
3. If either lookup succeeds, fail with `BINARY_ALREADY_EXISTS`.
4. Otherwise create and ingest a new binary.

A hash match wins across filenames. Renaming the same executable or changing `binary.name` in a JSON export does not make it a new binary.

A filename match is also rejected when the hash differs. The caller must choose a different name before importing changed content that reuses an existing `(name, version)`.

The error details identify how the duplicate was detected:

```json
{
  "match": "sha256",
  "existingBinaryId": 42,
  "existingName": "redtest.exe",
  "existingVersion": ""
}
```

`match` is either `sha256` or `filename`.

The duplicate lookup is executed inside the ingestion write transaction. This prevents two concurrent imports from both passing a separate preflight check before either writes its row.

## Public mode

Public mode randomizes the submitted binary name in the backend for both JSON and raw executable imports. The stored name has the form:

```text
<four random lowercase letters>_<submitted name>
```

For example:

```text
abcd_redtest.exe
```

Public mode deliberately permits multiple imports of identical content. SHA-256 is persisted and indexed, but it is not used to reject a public import.

Public imports remain non-overwriting:

- Every import normally receives a new randomized name and creates a new row.
- If randomization produces an already-existing `(name, version)`, the import fails with `BINARY_ALREADY_EXISTS` rather than refreshing that row.
- The frontend does not offer overwrite controls in public mode.

## Raw executable flow

For `POST /api/v1/binaries/decompile`:

1. The request body is streamed to a UUID-named staging file.
2. GraphRev computes SHA-256 over that staged file's original bytes.
3. The internal decompiler processes the staged executable and writes a staged JSON export.
4. GraphRev parses the generated export.
5. GraphRev replaces staging-derived metadata with user-facing metadata:
   - `binary.name` becomes the submitted `name` query parameter.
   - `binary.version` becomes the submitted `version` query parameter.
   - `binary.sourcePath` becomes the submitted name.
   - `binary.sha256` becomes GraphRev's computed digest.
6. The normal JSON adapter and ingestion pipeline persist the result.

Hashing the original bytes is important because both staging filenames are random UUIDs and the generated JSON is not binary content identity.

## JSON export contract

The supported binary metadata shape includes:

```json
{
  "binary": {
    "name": "redtest.exe",
    "version": "",
    "sourcePath": "/C:/Users/hacker/Desktop/redtest.exe",
    "analysisImageBase": 5368709120,
    "sha256": "803cc9853cdf9df8e474e2bac41f187d6acb91709d3e72d5af97cc2840230f42",
    "functionCount": 620,
    "edgeCount": 1334
  }
}
```

`sha256` is optional for backward compatibility. `functionCount` and `edgeCount` remain informational; ingestion derives actual counts from the imported function and edge records.

## Persistence

The `binaries` table stores:

- `name`
- `version`
- `source_path`
- `analysis_image_base`
- `sha256`
- view and timestamp metadata

Relevant constraints and indexes:

- `ux_binaries_name_version`: unique `(name, version)`
- `ix_binaries_sha256`: non-unique index on `sha256`

Migration `0011_add_binary_sha256.py` adds the nullable hash column and index.

## Main implementation locations

- Import schema and hash validation: `backend/src/graphrev/schemas/ingest.py`
- Raw executable hashing and metadata replacement: `backend/src/graphrev/ingestion/import_jobs.py`
- Adapter propagation: `backend/src/graphrev/adapters/ghidra/base.py` and `file.py`
- Transactional duplicate policy: `backend/src/graphrev/ingestion/pipeline.py`
- Public name randomization: `backend/src/graphrev/services/binary_service.py`
- Database lookup and persistence: `backend/src/graphrev/repositories/binaries.py`
- ORM model: `backend/src/graphrev/db/models.py`
- Migration: `backend/migrations/versions/0011_add_binary_sha256.py`
- Import UI: `frontend/src/features/sidebar/ImportBinaryButton.tsx`

## Future-change checklist

When modifying this behavior, verify all of the following explicitly:

- Whether content identity or display filename should win for the new flow.
- Whether the change affects private mode, public mode, or both.
- Whether duplicate content should be rejected, refresh an existing row, or create another row.
- Whether the browser-selected JSON filename must be sent separately from `binary.name`.
- Whether `version` remains part of fallback identity.
- Whether raw-upload duplicate detection should occur before running the expensive decompiler.
- Whether a database-level uniqueness mechanism is needed for concurrent private imports; the current hash index is non-unique to support public copies.
- Whether API error details or frontend duplicate messaging need updates.
- Whether legacy rows with `sha256 IS NULL` need backfilling.

Regression coverage belongs in:

- `backend/tests/ingestion/test_file_import.py`
- `backend/tests/api/test_binaries_api.py`
- `backend/tests/repositories/test_binaries.py`
- `backend/tests/db/test_schema_snapshot.py`
- `frontend/src/features/sidebar/ImportBinaryButton.test.tsx`
