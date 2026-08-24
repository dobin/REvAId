"""Shared fake-summary corpus for mock adapters (UI development, demos).

This module exists so **both** mock adapters agree on the same fake LLM
content instead of drifting apart:

- ``adapters/ghidra/mock.py::seed_mock_summaries`` uses it to pre-seed 15
  functions as ``summary_status='ready'`` at ingest time (CLI-only path,
  bypasses the summarisation queue entirely).
- ``adapters/llm/mock.py::MockLlmAdapter`` uses it so that a summary
  actually generated through the real queue/worker/SSE pipeline reads like
  real analyst content instead of the literal string ``"<name>: mock
  summary"``.

It is a plain data + pure-function module (no adapter Protocol, no I/O), so
it may be imported directly by both ``adapters/ghidra/mock.py`` and
``adapters/llm/mock.py`` without tripping the import-linter "only
adapters/*/base may be imported outside their own package" contract — that
contract only forbids importing a *concrete adapter implementation*
(``.mock``/``.rest``/``.litellm_adapter``/``.opencode_adapter``) from
outside its own adapter package; this module is neither.
"""

from __future__ import annotations

import hashlib

#: name_ghidra -> (summary_short, summary_long). Hand-written so the mock
#: corpus reads like plausible analyst output for the 15 functions that
#: `adapters/ghidra/mock.py::_build_acme_exe`/`_build_libparse_dll` name
#: explicitly (main, the three fan-in hubs, the two dispatchers, the
#: recursion/mutual-recursion pair, and the four-deep parse chain).
MOCK_SUMMARIES: dict[str, tuple[str, str]] = {
    "main": (
        "Program entry point; initialises subsystems and dispatches to the main event loop.",
        (
            "Parses command-line arguments and environment variables, then calls check_config "
            "to validate the runtime configuration. Initialises the logging subsystem and the "
            "memory allocator before handing control to the primary dispatch loop. Returns 0 on "
            "clean exit or a non-zero error code if any subsystem fails to initialise."
        ),
    ),
    "check_config": (
        "Validates the global configuration struct; returns non-zero if any required "
        "field is absent.",
        (
            "Iterates over every field in the config struct and checks that mandatory values are "
            "non-NULL and within their documented ranges. Emits a diagnostic message to stderr for "
            "each violation found. Called both directly from main and transitively from several "
            "entry_child handlers, giving it a fan-in of 3. Does not modify any global state."
        ),
    ),
    "dispatch_large": (
        "Central opcode dispatcher; routes execution to one of 300+ handler functions "
        "based on the input byte.",
        (
            "Implements a jump-table dispatch over the full 8-bit opcode space. Each case invokes "
            "a dedicated handler from the utility pool, making this function the primary fan-out "
            "hub of the binary. Uses indirect calls (computed branch through a function pointer "
            "table) so static analysis cannot fully resolve all callee targets. Has no meaningful "
            "return value; side effects are owned by the individual handlers."
        ),
    ),
    "dispatch_small": (
        "Lightweight secondary dispatcher handling 34 specialised opcodes that bypass "
        "the main table.",
        (
            "Covers opcodes that require pre-processing before the main dispatch loop, such as "
            "prefix bytes and escape sequences. Decodes the next byte to determine the secondary "
            "opcode and delegates to the appropriate handler. Falls back to an error handler if "
            "the opcode is not in the expected range."
        ),
    ),
    "mem_copy_block": (
        "High-throughput block copy; called by ~291 callers as the canonical "
        "memory-copy primitive.",
        (
            "Copies `len` bytes from `src` to `dst` using SIMD-aligned 16-byte chunks where "
            "possible, falling back to a byte loop for the remainder. Handles overlapping regions "
            "by delegating to memmove when src < dst + len. Is the most-called function in the "
            "binary; all heap-manipulation paths eventually reach it."
        ),
    ),
    "mem_set_block": (
        "Fills a memory region with a repeating byte value; the primary zeroing primitive.",
        (
            "Accepts a destination pointer, a fill byte, and a length. Uses 8-byte store "
            "instructions on aligned addresses and a scalar tail loop for the remainder. "
            "Frequently used to zero-initialise stack frames and heap allocations. "
            "Approximately 120 callers across the binary."
        ),
    ),
    "str_length": (
        "Null-terminated string length; thin wrapper over the platform strlen with bounds check.",
        (
            "Walks the string one byte at a time until it finds a NUL terminator or reaches "
            "the optional `max_len` guard, whichever comes first. Returns the number of bytes "
            "before the terminator. The bounds-checking wrapper is called in preference to "
            "raw strlen wherever the input may not be NUL-terminated within a trusted buffer."
        ),
    ),
    "walk_tree_recursive": (
        "Depth-first tree traversal; recurses into each child node before processing "
        "the current one.",
        (
            "Processes an AST-like node tree in post-order. For each node it first "
            "recurses into all child pointers, then invokes the registered visitor "
            "callback on the current node. The recursion depth is bounded by the tree "
            "height; no explicit stack limit is enforced, so deeply nested inputs may "
            "overflow the call stack."
        ),
    ),
    "eval_expr": (
        "Evaluates a full expression node by delegating term parsing to eval_term.",
        (
            "Implements the expression grammar rule: expr ::= term (('+' | '-') term)*. "
            "Calls eval_term for each operand and folds the results left-to-right using the "
            "arithmetic operator. Mutually recursive with eval_term for handling parenthesised "
            "sub-expressions. Returns the computed integer value of the expression."
        ),
    ),
    "eval_term": (
        "Evaluates a term node; mutually recursive with eval_expr for nested "
        "parenthesised expressions.",
        (
            "Implements the term grammar rule: term ::= factor (('*' | '/') factor)*. "
            "Delegates to eval_expr when it encounters a left parenthesis, creating mutual "
            "recursion for arbitrarily nested groupings. Division by zero is not guarded — "
            "callers are expected to validate inputs before invoking this function."
        ),
    ),
    "parse_document": (
        "Top-level entry point for the libparse document parser; drives the parse_section chain.",
        (
            "Initialises the parser context from the provided byte buffer and its length, then "
            "calls parse_section for each top-level section delimiter encountered. Accumulates "
            "section results into the caller-supplied document struct. Returns the number of "
            "sections parsed, or -1 if the document header is malformed."
        ),
    ),
    "parse_section": (
        "Parses one document section header and delegates field parsing to parse_field.",
        (
            "Reads the section type tag and byte length from the current buffer position, "
            "advances the cursor, then iterates over the section body calling parse_field for "
            "each field descriptor found. Validates the section checksum after all fields are "
            "consumed and returns an error code if it does not match."
        ),
    ),
    "parse_field": (
        "Parses a single field descriptor; delegates value decoding to parse_value.",
        (
            "Reads the field ID and type tag, dispatches to parse_value for the payload bytes, "
            "and stores the result in the section's field table. Unknown field IDs are skipped "
            "with a warning rather than treated as hard errors, maintaining forward compatibility "
            "with newer document versions."
        ),
    ),
    "parse_value": (
        "Decodes a typed value payload from the raw byte stream.",
        (
            "Handles the full set of primitive types: int8, int16, int32, int64, float32, "
            "float64, boolean, and variable-length UTF-8 strings. For string values, allocates "
            "a heap buffer and copies the bytes; the caller owns the allocation. Returns a "
            "tagged union holding the decoded value and its type discriminant."
        ),
    ),
    "parse_literal": (
        "Reads a raw literal byte sequence without type interpretation.",
        (
            "Copies exactly `len` bytes from the current stream position into the provided "
            "output buffer and advances the cursor. Used for opaque blob fields whose "
            "content is not inspected by the parser itself. Returns the number of bytes "
            "actually read, which may be less than `len` if the stream ends early."
        ),
    ),
}

#: Generic phrasing templates for functions with no hand-written corpus
#: entry. Picked deterministically per-name (via a hash) so a given function
#: always gets the same fallback text, and different functions don't all
#: read identically in a demo.
_FALLBACK_SHORT_TEMPLATES: tuple[str, ...] = (
    "Helper routine; behaviour inferred from {basis}.",
    "Utility function called from {callee_note}; no distinguishing side effects observed.",
    "Small internal routine; likely a leaf helper based on {basis}.",
    "Auxiliary function; purpose not fully determined from {basis} alone.",
)

_FALLBACK_LONG_TEMPLATES: tuple[str, ...] = (
    (
        "Analysis based on {basis} suggests this is a supporting routine rather than a "
        "primary entry point. {callee_clause}No notable control-flow anomalies (unbounded "
        "recursion, indirect calls) were observed. Treat this summary as provisional pending "
        "manual review."
    ),
    (
        "This function's behaviour was inferred from {basis} without additional context "
        "(analyst notes, caller naming). {callee_clause}It appears to perform a narrowly "
        "scoped operation typical of an internal helper. Confidence in this summary is low; "
        "revisit after examining its callers."
    ),
    (
        "Limited evidence — {basis} — was available for this function. {callee_clause}It does "
        "not appear to be a program entry point or a widely shared utility. Manual analyst "
        "review is recommended before relying on this summary."
    ),
)


def fallback_summary(
    name: str,
    address: int,
    *,
    has_code_c: bool,
    callee_count: int,
) -> tuple[str, str]:
    """Plausible-sounding placeholder prose for a function with no
    hand-written corpus entry (i.e. not one of the 15 :data:`MOCK_SUMMARIES`
    keys). Deterministic in ``name`` so the same function always gets the
    same fallback text across calls/processes given the same inputs.
    """
    digest = hashlib.sha256(f"{name}:{address:x}".encode()).digest()
    short_template = _FALLBACK_SHORT_TEMPLATES[digest[0] % len(_FALLBACK_SHORT_TEMPLATES)]
    long_template = _FALLBACK_LONG_TEMPLATES[digest[1] % len(_FALLBACK_LONG_TEMPLATES)]

    basis = "decompiled C" if has_code_c else "disassembly only"
    if callee_count == 0:
        callee_note = "no observed callees"
        callee_clause = "It has no observed callees, consistent with a leaf routine. "
    elif callee_count == 1:
        callee_note = "a single callee"
        callee_clause = "It calls exactly one other function. "
    else:
        callee_note = f"{callee_count} observed callees"
        callee_clause = f"It calls {callee_count} other functions. "

    short = short_template.format(basis=basis, callee_note=callee_note)[:120]
    long_ = long_template.format(basis=basis, callee_clause=callee_clause)
    return short, long_
