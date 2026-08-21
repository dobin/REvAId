"""`is_utility_effective` (E2b): follows utility_override, usable in ORDER BY."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Function


def _now() -> str:
    return utc_now_iso()


@pytest.mark.asyncio
async def test_is_utility_effective_follows_override(session: AsyncSession) -> None:
    binary = Binary(name="acme.exe", version="1.0", created_at=_now(), updated_at=_now())
    session.add(binary)
    await session.flush()

    computed_true = Function(
        binary_id=binary.id,
        address=0x1,
        name_ghidra="a",
        is_utility=True,
        created_at=_now(),
        updated_at=_now(),
    )
    computed_false = Function(
        binary_id=binary.id,
        address=0x2,
        name_ghidra="b",
        is_utility=False,
        created_at=_now(),
        updated_at=_now(),
    )
    overridden_never = Function(
        binary_id=binary.id,
        address=0x3,
        name_ghidra="c",
        is_utility=True,
        utility_override="never",
        created_at=_now(),
        updated_at=_now(),
    )
    overridden_always = Function(
        binary_id=binary.id,
        address=0x4,
        name_ghidra="d",
        is_utility=False,
        utility_override="always",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add_all([computed_true, computed_false, overridden_never, overridden_always])
    await session.commit()

    for fn in (computed_true, computed_false, overridden_never, overridden_always):
        await session.refresh(fn)

    assert computed_true.is_utility_effective is True
    assert computed_false.is_utility_effective is False
    assert overridden_never.is_utility_effective is False
    assert overridden_always.is_utility_effective is True


@pytest.mark.asyncio
async def test_is_utility_effective_usable_in_order_by(session: AsyncSession) -> None:
    binary = Binary(name="acme.exe", version="1.0", created_at=_now(), updated_at=_now())
    session.add(binary)
    await session.flush()

    session.add_all(
        [
            Function(
                binary_id=binary.id,
                address=0x1,
                name_ghidra="utility_fn",
                is_utility=True,
                created_at=_now(),
                updated_at=_now(),
            ),
            Function(
                binary_id=binary.id,
                address=0x2,
                name_ghidra="primary_fn",
                is_utility=False,
                created_at=_now(),
                updated_at=_now(),
            ),
        ]
    )
    await session.commit()

    rows = (
        (
            await session.execute(
                select(Function.name_ghidra).order_by(
                    Function.is_utility_effective.asc(), Function.name_ghidra
                )
            )
        )
        .scalars()
        .all()
    )
    assert rows == ["primary_fn", "utility_fn"]
