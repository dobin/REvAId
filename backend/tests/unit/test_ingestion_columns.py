"""The A3 pre-guard — the strongest available guard against the PRD's "single
worst failure this product can have": ingestion silently clobbering LLM- or
analyst-owned columns on re-ingest.
"""

from __future__ import annotations

from graphrev.db.models import INGESTION_OWNED_COLUMNS

FORBIDDEN_COLUMNS = frozenset(
    {
        "summary_short",
        "summary_long",
        "summary_status",
        "summary_model",
        "summary_adapter",
        "summary_error_code",
        "summary_low_confidence",
        "summary_generated_at",
        "summary_input_hash",
        "name_analyst",
        "notes",
        "notes_updated_at",
        "utility_override",
    }
)


def test_ingestion_owned_columns_excludes_llm_and_analyst_fields() -> None:
    overlap = INGESTION_OWNED_COLUMNS & FORBIDDEN_COLUMNS
    assert overlap == set(), f"Ingestion must never own: {overlap}"


def test_ingestion_owned_columns_is_non_empty() -> None:
    # Sanity check: the frozenset should actually list the ground-truth columns
    # ingestion IS allowed to touch, not be empty by omission.
    assert "name_ghidra" in INGESTION_OWNED_COLUMNS
    assert "fan_in" in INGESTION_OWNED_COLUMNS
