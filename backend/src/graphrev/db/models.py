"""SQLAlchemy 2.0 typed ORM models — the authoritative schema (TAD §3.3).

Six tables: ``binaries``, ``functions``, ``edges``, ``views``, ``view_nodes``,
``app_meta``. ``app_meta`` is a TAD addition beyond the PRD's five-table sketch
(B1), required by F1b to detect a threshold change between restarts without
re-ingestion (docs/adr/0003).

Deviations from the TAD §3.3 DDL text, both locked in this session:
  * ``edges.kind`` CHECK is narrowed to ``('call')`` — PRD: "the only value in
    M0"; TAD's own argument for closed-enum strictness favors this narrower
    constraint (docs/adr/0004).
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

from graphrev.db.enums import (
    EDGE_KIND_VALUES,
    FUNCTION_KIND_VALUES,
    ORIGIN_KIND_VALUES,
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
    # Ghidra's static program image base captured at export time. This is
    # ingestion-owned metadata used to translate ASLR runtime VAs; it is
    # nullable for legacy/non-Ghidra imports that did not report it.
    analysis_image_base: Mapped[int | None] = mapped_column(default=None)
    # Circular FK with `views` (B16 <-> B10): declared with use_alter so Alembic
    # emits it as a separate ALTER after `views` exists.
    last_view_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "views.id", ondelete="SET NULL", use_alter=True, name="fk_binaries_last_view_id_views"
        ),
        default=None,
    )
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
    views: Mapped[list[View]] = relationship(
        back_populates="binary",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="View.binary_id",
    )

    __table_args__ = (UniqueConstraint("name", "version", name="ux_binaries_name_version"),)


class Function(Base):
    __tablename__ = "functions"

    id: Mapped[int] = mapped_column(primary_key=True)
    binary_id: Mapped[int] = mapped_column(ForeignKey("binaries.id", ondelete="CASCADE"))

    # -- ground truth (ingestion-owned; overwritten on re-ingest) ----------
    address: Mapped[int] = mapped_column()  # AS7: int; hex is display-only
    name_ghidra: Mapped[str] = mapped_column()
    parameters: Mapped[str] = mapped_column(default="[]")  # JSON [{ordinal,name,type}]
    signature: Mapped[str | None] = mapped_column(default=None)
    assembly: Mapped[str | None] = mapped_column(default=None)  # NULL for placeholder/import (B17)
    code_c: Mapped[str | None] = mapped_column(default=None)
    kind: Mapped[str] = mapped_column(default="normal")
    placeholder_module: Mapped[str | None] = mapped_column(default=None)  # D35a
    #: I4/§5.1: true when Ghidra could not statically resolve every call
    #: target (indirect/computed calls) — feeds `mayBeIncomplete` on the
    #: callees neighbour page. Ground-truth/ingestion-owned, like `kind`.
    has_indirect_calls: Mapped[bool] = mapped_column(default=False)
    fan_in: Mapped[int] = mapped_column(default=0)  # A7a
    fan_out: Mapped[int] = mapped_column(default=0)
    is_utility: Mapped[bool] = mapped_column(default=False)  # derived at ingest/startup (F1b)

    # -- LLM-owned (NEVER touched by ingestion — A3) -----------------------
    summary_short: Mapped[str | None] = mapped_column(default=None)
    summary_long: Mapped[str | None] = mapped_column(default=None)
    summary_status: Mapped[str] = mapped_column(default="none")
    summary_model: Mapped[str | None] = mapped_column(default=None)
    #: I13/AM4: which adapter produced this summary ("mock"/"litellm"/...).
    #: Nullable, no CHECK (see migration 0005) — not surfaced in the UI yet.
    summary_adapter: Mapped[str | None] = mapped_column(default=None)
    summary_error_code: Mapped[str | None] = mapped_column(default=None)
    summary_low_confidence: Mapped[bool] = mapped_column(default=False)
    summary_generated_at: Mapped[str | None] = mapped_column(default=None)
    summary_input_hash: Mapped[str | None] = mapped_column(default=None)  # C10
    #: C13 (auto-display variant): the LLM-proposed function name. LLM-owned
    #: like `summary_*` (never touched by ingestion, A3) but participates in
    #: the *display* precedence `name_analyst ?? name_llm ?? name_ghidra` —
    #: it never overwrites either stored name.
    name_llm: Mapped[str | None] = mapped_column(default=None)

    # -- analyst-owned (NEVER touched by ingestion — A3) -------------------
    name_analyst: Mapped[str | None] = mapped_column(default=None)  # <=128 chars
    notes: Mapped[str] = mapped_column(default="")
    notes_updated_at: Mapped[str | None] = mapped_column(default=None)
    utility_override: Mapped[str | None] = mapped_column(default=None)  # D36
    # I3: "is this an entry point" (E1b suggestions). Analyst-owned by
    # construction — ingestion supplies an initial value only on first
    # INSERT (e.g. the mock adapter flags `main`/module roots) and never
    # overwrites it on re-ingest, exactly like `utility_override`; a future
    # PATCH (I4) lets the analyst toggle it directly.
    is_entry_point: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[str] = mapped_column()
    updated_at: Mapped[str] = mapped_column()

    # E2b: effective classification, computed in SQL so rows arrive pre-ordered.
    # VIRTUAL (not STORED) so future Alembic ADD COLUMN migrations stay legal
    # in SQLite; SQLite still indexes virtual generated columns.
    is_utility_effective: Mapped[bool] = mapped_column(
        Computed(
            "CASE utility_override WHEN 'always' THEN 1 WHEN 'never' THEN 0 ELSE is_utility END",
            persisted=False,
        ),
    )

    binary: Mapped[Binary] = relationship(back_populates="functions", foreign_keys=[binary_id])

    __table_args__ = (
        UniqueConstraint("binary_id", "address", name="ux_functions_binary_address"),  # B2
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
        Index("ix_functions_binary_name", "binary_id", "name_ghidra"),
        Index("ix_functions_binary_analystname", "binary_id", "name_analyst"),
        Index("ix_functions_status", "summary_status"),  # C5b sweep
        Index("ix_functions_fanin", "binary_id", "fan_in"),  # E1b entry points
        Index("ix_functions_utility_eff", "binary_id", "is_utility_effective"),
        Index("ix_functions_binary_entrypoint", "binary_id", "is_entry_point"),  # E1b
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


class View(Base):
    __tablename__ = "views"

    id: Mapped[int] = mapped_column(primary_key=True)
    binary_id: Mapped[int] = mapped_column(ForeignKey("binaries.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column()
    # B10a: "may be NULL for an empty view"; nulled if the function is deleted.
    root_function_id: Mapped[int | None] = mapped_column(
        ForeignKey("functions.id", ondelete="SET NULL"), default=None
    )
    camera_x: Mapped[float] = mapped_column(default=0.0)
    camera_y: Mapped[float] = mapped_column(default=0.0)
    camera_zoom: Mapped[float] = mapped_column(default=1.0)
    created_at: Mapped[str] = mapped_column()
    updated_at: Mapped[str] = mapped_column()

    binary: Mapped[Binary] = relationship(back_populates="views", foreign_keys=[binary_id])
    nodes: Mapped[list[ViewNode]] = relationship(
        back_populates="view",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="ViewNode.view_id",
    )

    __table_args__ = (Index("ix_views_binary", "binary_id"),)


class ViewNode(Base):
    __tablename__ = "view_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    view_id: Mapped[int] = mapped_column(ForeignKey("views.id", ondelete="CASCADE"))
    function_id: Mapped[int] = mapped_column(ForeignKey("functions.id", ondelete="CASCADE"))
    visible: Mapped[bool] = mapped_column(default=True)
    collapsed: Mapped[bool] = mapped_column(default=False)
    color: Mapped[str | None] = mapped_column(default=None)  # D16: palette token, not hex
    pos_x: Mapped[float] = mapped_column(default=0.0)
    pos_y: Mapped[float] = mapped_column(default=0.0)
    pinned: Mapped[bool] = mapped_column(default=False)  # D15

    # B4b / D8b: sole source of canvas edges.
    origin_function_id: Mapped[int | None] = mapped_column(
        ForeignKey("functions.id", ondelete="SET NULL"), default=None
    )
    origin_kind: Mapped[str] = mapped_column(default="root")
    origin_implied: Mapped[bool] = mapped_column(default=False)  # dashed edge

    created_at: Mapped[str] = mapped_column()
    updated_at: Mapped[str] = mapped_column()

    view: Mapped[View] = relationship(back_populates="nodes", foreign_keys=[view_id])

    __table_args__ = (
        UniqueConstraint("view_id", "function_id", name="ux_view_nodes_view_id_function_id"),
        CheckConstraint(
            f"origin_kind IN {_sql_in_list(ORIGIN_KIND_VALUES)}", name="origin_kind_valid"
        ),
        Index("ix_view_nodes_view", "view_id", "visible"),
        Index("ix_view_nodes_origin", "origin_function_id"),
    )


class AppMeta(Base):
    """Small key/value store for F1b's "last applied threshold" bookkeeping.

    A TAD addition beyond the PRD's five named tables (B1); required so the
    startup hook can detect a config change without re-ingestion.
    """

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column()


#: A3 guard: columns ingestion is allowed to overwrite on re-ingest. Anything
#: LLM-owned or analyst-owned must be absent — enforced by
#: tests/unit/test_ingestion_columns.py, the PRD's single worst-failure guard.
INGESTION_OWNED_COLUMNS: frozenset[str] = frozenset(
    {
        "binary_id",
        "address",
        "name_ghidra",
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
