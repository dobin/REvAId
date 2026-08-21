"""Ghidra adapter package.

This ``__init__.py`` is the **only** module allowed to import
``graphrev.adapters.ghidra.mock``/``.rest`` directly — every other caller
(``ingestion``, ``cli``, ``services``, ...) must go through
:func:`create_adapter` and the :mod:`graphrev.adapters.ghidra.base` Protocol,
per the ``import-linter`` "Only adapters/*/base may be imported outside their
own package" contract in ``pyproject.toml``.
"""

from __future__ import annotations

from graphrev.adapters.ghidra.base import GhidraAdapter
from graphrev.core.config import GhidraAdapterName


class GhidraAdapterNotImplementedError(NotImplementedError):
    """Raised for an adapter name that has no implementation yet (e.g. `rest`, M1)."""


def create_adapter(name: GhidraAdapterName, *, seed: int = 1337) -> GhidraAdapter:
    """Select a `GhidraAdapter` implementation by name (A2, A5).

    ``seed`` is only meaningful for ``"mock"`` (A2's determinism requirement);
    a real adapter ignores it.
    """
    if name == "mock":
        from graphrev.adapters.ghidra.mock import MockGhidraAdapter

        return MockGhidraAdapter(seed=seed)
    if name == "rest":
        raise GhidraAdapterNotImplementedError(
            "The 'rest' Ghidra adapter is not implemented until Increment I12 (M1). "
            "Use --adapter mock for now."
        )
    raise GhidraAdapterNotImplementedError(f"Unknown Ghidra adapter: {name!r}")


__all__ = ["GhidraAdapter", "GhidraAdapterNotImplementedError", "create_adapter"]
