"""Reachability checks for the optional local Kuna executable."""

from __future__ import annotations

import asyncio
from pathlib import Path


async def check_decompiler_health(executable: str | None) -> tuple[bool, str]:
    """Verify the configured Kuna path and version without analyzing a binary."""
    if not executable:
        return False, "No decompiler executable is configured."
    path = Path(executable)
    if not path.is_file():
        return False, "Configured decompiler path is not a file."
    if not path.stat().st_mode & 0o111:
        return False, "Configured decompiler is not executable."
    try:
        process = await asyncio.create_subprocess_exec(
            str(path),
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await asyncio.wait_for(process.communicate(), timeout=5)
    except (OSError, TimeoutError):
        return False, "Could not run configured decompiler."
    version = output.decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        return False, "Configured decompiler version check failed."
    if "kuna" not in version.lower():
        return False, "Configured executable is not Kuna."
    return True, version[:200] or "Kuna is available."
