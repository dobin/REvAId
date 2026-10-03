"""SQLAlchemy 2.0 typed ORM models — the authoritative schema (TAD §3.3).

Analysis owns ``binaries``, ``functions``, ``edges``, and ``app_meta``.
``app_meta`` is a TAD addition beyond the PRD's five-table sketch
(B1), required by F1b to detect a threshold change between restarts without
re-ingestion.

Deviations from the TAD §3.3 DDL text, both locked in this session:
  * ``edges.kind`` CHECK is narrowed to ``('call')`` — PRD: "the only value in
    M0"; TAD's own argument for closed-enum strictness favors this narrower
    constraint.
  * ``summary_status`` CHECK keeps all five values including ``'stale'``.

All timestamps are ISO-8601 UTC strings stored as TEXT (never ``DateTime``) —
human-readable in a SQLite browser, per the TAD §3.3 design note.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    MetaData,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from revaid.db.enums import (
    DATA_ITEM_KIND_VALUES,
    EDGE_KIND_VALUES,
    FUNCTION_KIND_VALUES,
    LLM_WORKER_OUTCOME_VALUES,
    SUMMARY_STATUS_VALUES,
    UTILITY_OVERRIDE_VALUES,
)

# Naming convention: Alembic autogenerate must produce *stable* constraint and
# index names across runs, or the "0001_initial vs. Base.metadata" schema
# snapshot test (I1 exit criterion) would show spurious diffs on every rename.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_label)s",
    "uq": "ux_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _sql_in_list(values: tuple[str, ...]) -> str:
    """Render a tuple of strings as a SQL ``(a, b, c)`` list.

    ``repr()`` of a one-element Python tuple produces ``('call',)`` — the
    trailing comma is invalid inside a SQL ``IN (...)`` clause — so this
    formats each value explicitly instead of relying on tuple repr.
    """
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


class Binary(Base):
    __tablename__ = "binaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    version: Mapped[str] = mapped_column(default="")  # free text (AS11)
    source_path: Mapped[str | None] = mapped_column(default=None)
    # Content identity reported by JSON exporters or computed from a raw
    # upload before decompilation. Nullable for legacy adapters/exports.
    sha256: Mapped[str | None] = mapped_column(default=None)
    # Ghidra's static program image base captured at export time. This is
    # ingestion-owned metadata used to translate ASLR runtime VAs; it is
    # nullable for legacy/non-Ghidra imports that did not report it.
    analysis_image_base: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[str] = mapped_column()  # ISO-8601 UTC
    updated_at: Mapped[str] = mapped_column()

    # passive_deletes=True: rely on the DB-level ON DELETE CASCADE (the source
    # of truth) instead of having the ORM also issue per-row DELETEs, which
    # can race with cascades that already fired via a different path (e.g.
    # binaries -> functions -> view_nodes vs. binaries -> views -> view_nodes).
    functions: Mapped[list[Function]] = relationship(
        back_populates="binary",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Function.binary_id",
    )
    edges: Mapped[list[Edge]] = relationship(
        back_populates="binary",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Edge.binary_id",
    )

    __table_args__ = (
        UniqueConstraint("name", "version", name="ux_binaries_name_version"),
        # Deliberately non-unique: public mode permits separate anonymous
        # imports of identical content under independently randomised names.
        Index("ix_binaries_sha256", "sha256"),
    )


class Function(Base):
    __tablename__ = "functions"

    id: Mapped[int] = mapped_column(primary_key=True)
    binary_id: Mapped[int] = mapped_column(ForeignKey("binaries.id", ondelete="CASCADE"))
    address: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column()
    parameters: Mapped[str] = mapped_column(default="[]")
    signature: Mapped[str | None] = mapped_column(default=None)
    assembly: Mapped[str | None] = mapped_column(default=None)
    code_c: Mapped[str | None] = mapped_column(default=None)
    kind: Mapped[str] = mapped_column(default="normal")
    placeholder_module: Mapped[str | None] = mapped_column(default=None)
    has_indirect_calls: Mapped[bool] = mapped_column(default=False)
    fan_in: Mapped[int] = mapped_column(default=0)
    fan_out: Mapped[int] = mapped_column(default=0)
    is_utility: Mapped[bool] = mapped_column(default=False)
    summary_short: Mapped[str | None] = mapped_column(default=None)
    summary_long: Mapped[str | None] = mapped_column(default=None)
    summary_status: Mapped[str] = mapped_column(default="none")
    summary_model: Mapped[str | None] = mapped_column(default=None)
    summary_adapter: Mapped[str | None] = mapped_column(default=None)
    summary_error_code: Mapped[str | None] = mapped_column(default=None)
    summary_low_confidence: Mapped[bool] = mapped_column(default=False)
    summary_generated_at: Mapped[str | None] = mapped_column(default=None)
    summary_input_hash: Mapped[str | None] = mapped_column(default=None)
    name_llm: Mapped[str | None] = mapped_column(default=None)
    name_analyst: Mapped[str | None] = mapped_column(default=None)
    notes: Mapped[str] = mapped_column(default="")
    notes_updated_at: Mapped[str | None] = mapped_column(default=None)
    utility_override: Mapped[str | None] = mapped_column(default=None)
    is_featured: Mapped[bool] = mapped_column(default=False)
    is_entry_point: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column()
    updated_at: Mapped[str] = mapped_column()
    is_utility_effective: Mapped[bool] = mapped_column(
        Computed(
            "CASE utility_override WHEN 'always' THEN 1 WHEN 'never' THEN 0 ELSE is_utility END",
            persisted=False,
        )
    )
    binary: Mapped[Binary] = relationship(back_populates="functions", foreign_keys=[binary_id])
    __table_args__ = (
        UniqueConstraint("binary_id", "address", name="ux_functions_binary_address"),
        CheckConstraint(f"kind IN {_sql_in_list(FUNCTION_KIND_VALUES)}", name="kind_valid"),
        CheckConstraint(
            f"summary_status IN {_sql_in_list(SUMMARY_STATUS_VALUES)}",
            name="summary_status_valid",
        ),
        CheckConstraint(
            "utility_override IS NULL OR utility_override IN "
            f"{_sql_in_list(UTILITY_OVERRIDE_VALUES)}",
            name="utility_override_valid",
        ),
        Index("ix_functions_binary_name", "binary_id", "name"),
        Index("ix_functions_binary_analystname", "binary_id", "name_analyst"),
        Index("ix_functions_status", "summary_status"),
        Index("ix_functions_fanin", "binary_id", "fan_in"),
        Index("ix_functions_utility_eff", "binary_id", "is_utility_effective"),
        Index("ix_functions_binary_entrypoint", "binary_id", "is_entry_point"),
    )


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    binary_id: Mapped[int] = mapped_column(ForeignKey("binaries.id", ondelete="CASCADE"))
    caller_id: Mapped[int] = mapped_column(ForeignKey("functions.id", ondelete="CASCADE"))
    callee_id: Mapped[int] = mapped_column(ForeignKey("functions.id", ondelete="CASCADE"))
    # Static first-call-site order from a schema-v2 Ghidra export. NULL means
    # the source did not report an order (for example, a legacy v1 export).
    callee_order: Mapped[int | None] = mapped_column(default=None)
    kind: Mapped[str] = mapped_column(default="call")

    binary: Mapped[Binary] = relationship(back_populates="edges", foreign_keys=[binary_id])

    __table_args__ = (
        UniqueConstraint("caller_id", "callee_id", name="ux_edges_pair"),  # B3; self-edges allowed
        CheckConstraint(f"kind IN {_sql_in_list(EDGE_KIND_VALUES)}", name="kind_valid"),
        CheckConstraint(
            "callee_order IS NULL OR callee_order >= 0", name="callee_order_nonnegative"
        ),
        Index("ix_edges_caller", "caller_id"),
        Index("ix_edges_callee", "callee_id"),
        Index("ix_edges_caller_callee_order", "caller_id", "callee_order"),
    )


class DataItem(Base):
    """A PE data location (.data/.rdata/...) referenced from function assembly.

    Populated only for binaries imported from a raw PE. References are
    recovered opportunistically from literal addresses in assembly text.
    """

    __tablename__ = "data_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    binary_id: Mapped[int] = mapped_column(ForeignKey("binaries.id", ondelete="CASCADE"))
    address: Mapped[int] = mapped_column()
    rva: Mapped[int] = mapped_column()
    section: Mapped[str] = mapped_column()
    kind: Mapped[str] = mapped_column()
    size: Mapped[int] = mapped_column(default=0)
    # Decoded string, import name ("DLL::Name"), or pointed-to string.
    value_text: Mapped[str | None] = mapped_column(default=None)
    target_address: Mapped[int | None] = mapped_column(default=None)
    preview_hex: Mapped[str | None] = mapped_column(default=None)
    is_writable: Mapped[bool] = mapped_column(default=False)
    ref_count: Mapped[int] = mapped_column(default=0)
    summary_llm: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[str] = mapped_column()

    __table_args__ = (
        UniqueConstraint("binary_id", "address", name="ux_data_items_binary_address"),
        CheckConstraint(f"kind IN {_sql_in_list(DATA_ITEM_KIND_VALUES)}", name="kind_valid"),
        Index("ix_data_items_binary_kind", "binary_id", "kind"),
        Index("ix_data_items_binary_section", "binary_id", "section"),
        Index("ix_data_items_binary_refcount", "binary_id", "ref_count"),
    )


class DataRef(Base):
    """A function -> data item reference at one instruction (like an edge)."""

    __tablename__ = "data_refs"

    id: Mapped[int] = mapped_column(primary_key=True)
    binary_id: Mapped[int] = mapped_column(ForeignKey("binaries.id", ondelete="CASCADE"))
    function_id: Mapped[int] = mapped_column(ForeignKey("functions.id", ondelete="CASCADE"))
    data_item_id: Mapped[int] = mapped_column(ForeignKey("data_items.id", ondelete="CASCADE"))
    instruction_address: Mapped[int] = mapped_column()
    instruction_text: Mapped[str] = mapped_column()
    source: Mapped[str] = mapped_column(default="asm-parse")

    __table_args__ = (
        UniqueConstraint(
            "function_id",
            "data_item_id",
            "instruction_address",
            name="ux_data_refs_function_item_instruction",
        ),
        Index("ix_data_refs_item", "data_item_id"),
        Index("ix_data_refs_function", "function_id"),
        Index("ix_data_refs_binary", "binary_id"),
    )


class AppMeta(Base):
    """Small key/value store for F1b's "last applied threshold" bookkeeping.

    A TAD addition beyond the PRD's five named tables (B1); required so the
    startup hook can detect a config change without re-ingestion.
    """

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column()


class LlmWorkerStatus(Base):
    """Latest meaningful provider outcome for an adapter/model pair.

    A one-row-per-configuration record survives process restarts while making
    no claim that the provider is reachable *right now*. It intentionally
    stores only a public error code; raw provider exceptions remain logs-only.
    """

    __tablename__ = "llm_worker_statuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    adapter: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column()
    outcome: Mapped[str] = mapped_column()
    observed_at: Mapped[str] = mapped_column()
    function_id: Mapped[int | None] = mapped_column(default=None)
    error_code: Mapped[str | None] = mapped_column(default=None)

    __table_args__ = (
        UniqueConstraint("adapter", "model", name="ux_llm_worker_statuses_adapter_model"),
        CheckConstraint(
            f"outcome IN {_sql_in_list(LLM_WORKER_OUTCOME_VALUES)}",
            name="outcome_valid",
        ),
        Index("ix_llm_worker_statuses_adapter_model", "adapter", "model"),
    )


INGESTION_OWNED_COLUMNS: frozenset[str] = frozenset(
    {
        "binary_id",
        "address",
        "name",
        "parameters",
        "signature",
        "assembly",
        "code_c",
        "kind",
        "placeholder_module",
        "has_indirect_calls",
        "fan_in",
        "fan_out",
        "is_utility",
        "updated_at",
    }
)
