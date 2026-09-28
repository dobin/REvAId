"""Viewer-owned SQLAlchemy models and metadata."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, MetaData, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from revaid_ui.db.enums import ORIGIN_KIND_VALUES


class ViewerBase(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_label)s",
            "uq": "ux_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def _sql_in_list(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


class View(ViewerBase):
    __tablename__ = "views"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Analysis IDs are external references; Viewer has no cross-store FK.
    binary_id: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column()
    root_function_id: Mapped[int | None] = mapped_column(default=None)
    camera_x: Mapped[float] = mapped_column(default=0.0)
    camera_y: Mapped[float] = mapped_column(default=0.0)
    camera_zoom: Mapped[float] = mapped_column(default=1.0)
    created_at: Mapped[str] = mapped_column()
    updated_at: Mapped[str] = mapped_column()

    nodes: Mapped[list[ViewNode]] = relationship(
        back_populates="view",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="ViewNode.view_id",
        order_by="ViewNode.id",
    )

    __table_args__ = (Index("ix_views_binary", "binary_id"),)


class BinaryUiState(ViewerBase):
    """Viewer-owned preferences keyed by an analysis binary identifier.

    Neither ID has a database FK because the referenced binary and view
    records live in the separate analysis/viewer API stores.
    """

    __tablename__ = "binary_ui_state"

    binary_id: Mapped[int] = mapped_column(primary_key=True)
    last_view_id: Mapped[int | None] = mapped_column(default=None)
    updated_at: Mapped[str] = mapped_column()


class ViewNode(ViewerBase):
    __tablename__ = "view_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    view_id: Mapped[int] = mapped_column(ForeignKey("views.id", ondelete="CASCADE"))
    # Function IDs are external analysis references, validated through A.
    function_id: Mapped[int] = mapped_column()
    visible: Mapped[bool] = mapped_column(default=True)
    collapsed: Mapped[bool] = mapped_column(default=False)
    color: Mapped[str | None] = mapped_column(default=None)  # D16: palette token, not hex
    pos_x: Mapped[float] = mapped_column(default=0.0)
    pos_y: Mapped[float] = mapped_column(default=0.0)
    pinned: Mapped[bool] = mapped_column(default=False)  # D15

    # B4b / D8b: sole source of canvas edges.
    origin_function_id: Mapped[int | None] = mapped_column(default=None)
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
