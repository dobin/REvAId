"""Assemble a :class:`SummaryRequest` from DB rows (C9).

This module assembles *data* only — prompt wording/content is explicitly out
of scope (`AS14`, docs/specs/PLAN-I7-I8-I9-I13.md). It reads the function's
own ground-truth columns plus the already-generated ``summary_short`` of its
callees (so a later prompt/agent can build on prior work), and nothing else.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.adapters.ghidra.base import RawParam
from graphrev.adapters.llm.base import SummaryRequest
from graphrev.core.errors import AppError, ErrorCode
from graphrev.db.models import Binary, Edge, Function


async def build_summary_request(session: AsyncSession, *, function_id: int) -> SummaryRequest:
    """Load ``function_id`` and its callees' short summaries into a
    :class:`SummaryRequest`. Raises :class:`AppError` (``FUNCTION_NOT_FOUND``)
    if the function does not exist."""
    fn = await session.get(Function, function_id)
    if fn is None:
        raise AppError(
            ErrorCode.FUNCTION_NOT_FOUND,
            f"No function {function_id}.",
            details={"functionId": function_id},
        )

    binary = await session.get(Binary, fn.binary_id)
    assert binary is not None  # FK guarantees this; never None in practice.

    callee_rows = (
        await session.execute(
            select(Function.name_analyst, Function.name_ghidra, Function.summary_short)
            .join(Edge, Edge.callee_id == Function.id)
            .where(Edge.caller_id == function_id, Function.summary_short.is_not(None))
            .order_by(Function.id.asc())
        )
    ).all()
    callee_summaries = tuple(
        (name_analyst or name_ghidra, summary_short)
        for name_analyst, name_ghidra, summary_short in callee_rows
        if summary_short is not None
    )

    raw_params: list[dict[str, object]] = json.loads(fn.parameters)
    parameters = tuple(
        RawParam(ordinal=p["ordinal"], name=p["name"], type=p["type"])  # type: ignore[typeddict-item]
        for p in raw_params
    )

    return SummaryRequest(
        address=fn.address,
        name=fn.name_ghidra,
        parameters=parameters,
        code_c=fn.code_c,
        assembly=fn.assembly,
        analyst_name=fn.name_analyst,
        notes=fn.notes or None,
        callee_summaries=callee_summaries,
        binary_name=binary.name,
        binary_version=binary.version,
        source_path=binary.source_path,
    )
