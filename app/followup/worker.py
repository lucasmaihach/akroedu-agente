from __future__ import annotations

import asyncio

import structlog

from app.followup.service import process_due_followups
from app.jobs.executor import process_due_pending_jobs, resume_pending_jobs_on_startup

logger = structlog.get_logger()


class FollowupWorker:
    def __init__(self, poll_seconds: int = 30):
        self.poll_seconds = poll_seconds
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        await resume_pending_jobs_on_startup()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("🕒 Follow-up worker iniciado.", poll_seconds=self.poll_seconds)

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop.set()
        await self._task
        logger.info("🛑 Follow-up worker encerrado.")

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await process_due_pending_jobs()
                await process_due_followups()
            except Exception as e:
                logger.error("Erro no loop do follow-up worker.", error=str(e))
            await asyncio.sleep(self.poll_seconds)
