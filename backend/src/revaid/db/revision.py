"""Analysis database migration-head verification."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


class MigrationNotAppliedError(RuntimeError):
    """Raised when the analysis database is not at the expected revision."""


def require_revision(revision: str | None, expected: str, store_name: str) -> None:
    if revision != expected:
        raise MigrationNotAppliedError(
            f"{store_name} database revision is {revision!r}; expected "
            f"{expected!r}. Run the corresponding `graphrev db migrate-{store_name.lower()}` first."
        )


async def read_revision(session_factory: Any, store_name: str) -> str:
    async with session_factory() as session:
        try:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            revision = result.scalar_one_or_none()
        except Exception as exc:
            raise MigrationNotAppliedError(
                f"{store_name} database has not been migrated. Run "
                f"`graphrev db migrate-{store_name.lower()}` first."
            ) from exc
    return revision or ""
