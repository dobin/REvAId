"""Process-local staged-file import jobs.

The manager deliberately separates request streaming from expensive ingestion:
the request only writes bounded bytes to disk, then a single SQLite-safe worker
per process imports the file. Jobs are ephemeral by design; a process restart
cleans staged files and loses their status.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.core.config import Settings
from graphrev.core.errors import AppError, ErrorCode
from graphrev.schemas.ingest import (
    ImportJobAcceptedDto,
    ImportJobPhase,
    ImportJobStatusDto,
)
from graphrev.services.binary_service import import_ghidra_export, load_ghidra_export_file


@dataclass
class _ImportJob:
    job_id: str
    path: Path
    bytes_received: int
    phase: ImportJobPhase = ImportJobPhase.QUEUED
    result: ImportJobStatusDto | None = None
    cancelled: bool = False
    done: asyncio.Event = field(default_factory=asyncio.Event)


class ImportJobManager:
    """Own staged imports and expose immutable status snapshots."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._staging_dir = Path(settings.import_staging_dir)
        self._queue: asyncio.Queue[_ImportJob | None] = asyncio.Queue()
        self._jobs: dict[str, _ImportJob] = {}
        self._workers: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        self._staging_dir.mkdir(parents=True, exist_ok=True)
        for _ in range(self._settings.import_worker_concurrency):
            self._workers.append(asyncio.create_task(self._run(), name="graphrev-import-worker"))

    async def stop(self) -> None:
        for _ in self._workers:
            await self._queue.put(None)
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        for job in self._jobs.values():
            job.path.unlink(missing_ok=True)

    def staging_path(self) -> Path:
        """Return a non-public unique path for one currently streaming upload."""
        return self._staging_dir / f"{uuid4()}.json"

    async def submit(self, path: Path, *, bytes_received: int) -> ImportJobAcceptedDto:
        job_id = str(uuid4())
        job = _ImportJob(job_id=job_id, path=path, bytes_received=bytes_received)
        job.result = ImportJobStatusDto(
            job_id=job_id,
            phase=job.phase,
            bytes_received=bytes_received,
        )
        self._jobs[job_id] = job
        await self._queue.put(job)
        return ImportJobAcceptedDto(
            job_id=job_id,
            phase=job.phase,
            bytes_received=bytes_received,
        )

    def status(self, job_id: str) -> ImportJobStatusDto:
        job = self._jobs.get(job_id)
        if job is None or job.result is None:
            raise AppError(ErrorCode.IMPORT_JOB_NOT_FOUND, f"No import job {job_id}.")
        return job.result.model_copy(deep=True)

    def cancel(self, job_id: str) -> ImportJobStatusDto:
        job = self._jobs.get(job_id)
        if job is None or job.result is None:
            raise AppError(ErrorCode.IMPORT_JOB_NOT_FOUND, f"No import job {job_id}.")
        if job.phase is ImportJobPhase.QUEUED:
            job.cancelled = True
            job.phase = ImportJobPhase.CANCELLED
            job.result = ImportJobStatusDto(
                job_id=job.job_id,
                phase=job.phase,
                bytes_received=job.bytes_received,
            )
            job.path.unlink(missing_ok=True)
            job.done.set()
        return job.result.model_copy(deep=True)

    async def _run(self) -> None:
        while (job := await self._queue.get()) is not None:
            try:
                if job.cancelled:
                    continue
                job.phase = ImportJobPhase.IMPORTING
                job.result = ImportJobStatusDto(
                    job_id=job.job_id,
                    phase=job.phase,
                    bytes_received=job.bytes_received,
                )
                document = await load_ghidra_export_file(job.path)
                result = await import_ghidra_export(self._session_factory, self._settings, document)
                samples = result.failures[: self._settings.import_failure_sample_limit]
                job.phase = ImportJobPhase.COMPLETED
                job.result = ImportJobStatusDto(
                    job_id=job.job_id,
                    phase=job.phase,
                    bytes_received=job.bytes_received,
                    result=result.model_copy(update={"failures": samples}),
                    failure_samples=samples,
                )
            except AppError as exc:
                job.phase = ImportJobPhase.FAILED
                job.result = ImportJobStatusDto(
                    job_id=job.job_id,
                    phase=job.phase,
                    bytes_received=job.bytes_received,
                    error_message=exc.message,
                )
            except Exception:
                job.phase = ImportJobPhase.FAILED
                job.result = ImportJobStatusDto(
                    job_id=job.job_id,
                    phase=job.phase,
                    bytes_received=job.bytes_received,
                    error_message="Import failed unexpectedly.",
                )
            finally:
                job.path.unlink(missing_ok=True)
                job.done.set()
                self._queue.task_done()