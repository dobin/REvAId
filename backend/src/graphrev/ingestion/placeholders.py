"""Placeholder function naming + materialisation (B17, D35a, Q24).

When ingestion finds an edge whose target address is not in the binary
currently being ingested — a call into a DLL when only the EXE was analysed,
or into an unanalysed module — it creates a real `functions` row with
`kind = 'placeholder'` instead of violating the `edges` foreign keys. The
call is then always visible in the neighbour table (D6/D7), fannable, and
summarisable from its name (low-confidence). A later full ingestion of that
module upgrades the row in place via the ordinary `(binary_id, address)`
UPSERT (`repositories.functions.upsert_function`) — no special-case upgrade
code is needed, because the placeholder is scoped to the *same* `binary_id`
as the binary being ingested right now.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.db.models import Function
from graphrev.repositories.functions import upsert_function


def placeholder_name(address: int, module: str | None) -> str:
    """`{module}!FUN_{address:08x}`, or bare `FUN_{address:08x}` if `module`
    is unknown."""
    fun = f"FUN_{address:08x}"
    if module:
        return f"{module}!{fun}"
    return fun


async def ensure_placeholder_function(
    session: AsyncSession,
    *,
    binary_id: int,
    address: int,
    module: str | None,
) -> int:
    """Idempotently create (or no-op if it already exists / is real) a
    `kind='placeholder'` function row for `address` under `binary_id`.

    Returns the function's id. Safe to call every time an edge's callee
    cannot be resolved within the binary currently being ingested — the
    underlying UPSERT is a no-op on an address that already has a `normal`
    (or otherwise real) row, so this never demotes an already-resolved
    function back to `placeholder`.
    """
    existing = (
        await session.execute(
            select(Function.id, Function.kind).where(
                Function.binary_id == binary_id, Function.address == address
            )
        )
    ).one_or_none()
    if existing is not None:
        # Already resolved (or already a placeholder) — never re-demote a
        # real row, and no need to re-insert an existing placeholder.
        return int(existing[0])

    function_id, _created = await upsert_function(
        session,
        binary_id=binary_id,
        address=address,
        name_ghidra=placeholder_name(address, module),
        kind="placeholder",
        placeholder_module=module,
    )
    return function_id
