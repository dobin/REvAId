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
from typing import Literal
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
    source_kind: Literal["json_export", "raw_binary"]
    binary_name: str | None = None
    binary_version: str = ""
    output_path: Path | None = None
    process: asyncio.subprocess.Process | None = None
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
            if job.process is not None and job.process.returncode is None:
                job.process.terminate()
            job.path.unlink(missing_ok=True)
            if job.output_path is not None:
                job.output_path.unlink(missing_ok=True)

    def staging_path(self, suffix: str = ".json") -> Path:
        """Return a non-public unique path for one currently streaming upload."""
        return self._staging_dir / f"{uuid4()}{suffix}"

    async def submit(
        self,
        path: Path,
        *,
        bytes_received: int,
        source_kind: Literal["json_export", "raw_binary"] = "json_export",
        binary_name: str | None = None,
        binary_version: str = "",
    ) -> ImportJobAcceptedDto:
        job_id = str(uuid4())
        job = _ImportJob(
            job_id=job_id,
            path=path,
            bytes_received=bytes_received,
            source_kind=source_kind,
            binary_name=binary_name,
            binary_version=binary_version,
        )
        job.result = ImportJobStatusDto(
            job_id=job_id,
            phase=job.phase,
            bytes_received=bytes_received,
            source_kind=source_kind,
        )
        self._jobs[job_id] = job
        await self._queue.put(job)
        return ImportJobAcceptedDto(
            job_id=job_id,
            phase=job.phase,
            bytes_received=bytes_received,
            source_kind=source_kind,
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
                source_kind=job.source_kind,
            )
            job.path.unlink(missing_ok=True)
            job.done.set()
        elif job.phase is ImportJobPhase.DECOMPILING and job.process is not None:
            job.cancelled = True
            job.process.terminate()
        return job.result.model_copy(deep=True)

    async def _run(self) -> None:
        while (job := await self._queue.get()) is not None:
            try:
                if job.cancelled:
                    continue
                if job.source_kind == "raw_binary":
                    job.phase = ImportJobPhase.DECOMPILING
                    job.result = self._status(job)
                    job.output_path = self.staging_path(".json")
                    await self._run_decompiler(job)
                    if job.cancelled:
                        job.phase = ImportJobPhase.CANCELLED
                        job.result = self._status(job)
                        continue
                    document = await load_ghidra_export_file(job.output_path)
                    # The exporter's input is an internal UUID path. Preserve
                    # only caller-supplied, user-facing metadata in GraphRev.
                    document = document.model_copy(
                        update={
                            "binary": document.binary.model_copy(
                                update={
                                    "name": job.binary_name,
                                    "version": job.binary_version,
                                    "source_path": job.binary_name,
                                }
                            )
                        }
                    )
                else:
                    document = await load_ghidra_export_file(job.path)
                job.phase = ImportJobPhase.IMPORTING
                job.result = self._status(job)
                result = await import_ghidra_export(self._session_factory, self._settings, document)
                samples = result.failures[: self._settings.import_failure_sample_limit]
                job.phase = ImportJobPhase.COMPLETED
                job.result = ImportJobStatusDto(
                    job_id=job.job_id,
                    phase=job.phase,
                    bytes_received=job.bytes_received,
                    source_kind=job.source_kind,
                    result=result.model_copy(update={"failures": samples}),
                    failure_samples=samples,
                )
            except AppError as exc:
                job.phase = ImportJobPhase.FAILED
                job.result = ImportJobStatusDto(
                    job_id=job.job_id,
                    phase=job.phase,
                    bytes_received=job.bytes_received,
                    source_kind=job.source_kind,
                    error_message=exc.message,
                    error_code=exc.code,
                )
            except Exception:
                job.phase = ImportJobPhase.FAILED
                job.result = ImportJobStatusDto(
                    job_id=job.job_id,
                    phase=job.phase,
                    bytes_received=job.bytes_received,
                    source_kind=job.source_kind,
                    error_message="Import failed unexpectedly.",
                )
            finally:
                job.path.unlink(missing_ok=True)
                if job.output_path is not None:
                    job.output_path.unlink(missing_ok=True)
                job.done.set()
                self._queue.task_done()

    def _status(self, job: _ImportJob) -> ImportJobStatusDto:
        return ImportJobStatusDto(
            job_id=job.job_id,
            phase=job.phase,
            bytes_received=job.bytes_received,
            source_kind=job.source_kind,
        )

    async def _run_decompiler(self, job: _ImportJob) -> None:
        executable = self._settings.decompiler_executable
        if executable is None or not Path(executable).is_file():
            raise AppError(
                ErrorCode.DECOMPILER_UNAVAILABLE, "The configured decompiler is unavailable."
            )
        assert job.output_path is not None
        job.process = await asyncio.create_subprocess_exec(
            executable,
            "graph-export",
            str(job.path),
            "-o",
            str(job.output_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        process = job.process
        try:
            return_code = await asyncio.wait_for(
                process.wait(), timeout=self._settings.decompiler_timeout_seconds
            )
        except TimeoutError as exc:
            process.terminate()
            try:
                await asyncio.wait_for(
                    process.wait(), timeout=self._settings.decompiler_kill_grace_seconds
                )
            except TimeoutError:
                process.kill()
                await process.wait()
            raise AppError(ErrorCode.DECOMPILER_TIMEOUT, "Decompiler timed out.") from exc
        finally:
            job.process = None
        if job.cancelled:
            return
        if return_code != 0:
            raise AppError(ErrorCode.DECOMPILER_FAILED, "Decompiler failed to export the binary.")
        if not job.output_path.is_file() or job.output_path.stat().st_size == 0:
            raise AppError(ErrorCode.DECOMPILER_FAILED, "Decompiler did not produce an export.")
        if job.output_path.stat().st_size > self._settings.decompiler_max_output_bytes:
            raise AppError(
                ErrorCode.DECOMPILER_OUTPUT_TOO_LARGE,
                "Decompiler output exceeds the configured limit.",
            )
