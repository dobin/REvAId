"""Function repository.

Only the ``INGESTION_OWNED_COLUMNS`` guard is needed in I1; the full UPSERT
repository (idempotent ingestion, A3) is built in I2. Re-exported here so
``graphrev.repositories.functions.INGESTION_OWNED_COLUMNS`` is the stable
import path callers use, even though the frozenset itself is defined next to
the model it guards.
"""

from __future__ import annotations

from graphrev.db.models import INGESTION_OWNED_COLUMNS

__all__ = ["INGESTION_OWNED_COLUMNS"]
