"""Viewer startup readiness behavior."""

from __future__ import annotations

import pytest

from revaid_ui.lifespan import wait_for_analysis


@pytest.mark.asyncio
async def test_wait_for_analysis_retries_until_ready() -> None:
    class DelayedAnalysis:
        def __init__(self) -> None:
            self.attempts = 0

        async def health(self) -> bool:
            self.attempts += 1
            if self.attempts == 1:
                raise ConnectionError("not listening yet")
            return self.attempts >= 3

    analysis = DelayedAnalysis()

    await wait_for_analysis(
        analysis,
        timeout_seconds=1,
        retry_interval_seconds=0.001,  # type: ignore[arg-type]
    )

    assert analysis.attempts == 3


@pytest.mark.asyncio
async def test_wait_for_analysis_times_out_if_service_never_becomes_ready() -> None:
    class UnavailableAnalysis:
        async def health(self) -> bool:
            return False

    with pytest.raises(RuntimeError, match="did not become ready"):
        await wait_for_analysis(
            UnavailableAnalysis(),
            timeout_seconds=0.001,
            retry_interval_seconds=0.001,  # type: ignore[arg-type]
        )
