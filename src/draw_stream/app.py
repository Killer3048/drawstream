"""Application bootstrap and lifecycle management."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import uvicorn

from .api.server import ControlServer
from .config import Settings, get_settings
from .donation.ingestor import DonationIngestor
from .gatekeeper import Gatekeeper
from .llm import LLMOrchestrator, LLMPlanError
from .logging import configure_logging
from .models import DonationEvent, RenderTask, RenderTaskType
from .queue import QueueManager
from .renderer.runtime import RendererRuntime

logger = logging.getLogger(__name__)


class DrawStreamApp:
    """Coordinates ingestion, orchestration, rendering, and API layers."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        configure_logging(self._settings.log_level)

        self._render_queue = QueueManager(self._settings.queue_max_size)
        self._renderer = RendererRuntime(self._render_queue, self._settings)
        self._gatekeeper = Gatekeeper()
        self._orchestrator = LLMOrchestrator(self._settings)
        self._control = ControlServer(self._render_queue, self._renderer, self._settings)
        self._ingestor = DonationIngestor(self._enqueue_donation, self._settings)

        self._donation_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._api_task: Optional[asyncio.Task[None]] = None
        self._api_server: Optional[uvicorn.Server] = None

    async def start(self) -> None:
        await self._renderer.start()
        await self._ingestor.start()
        self._worker_task = asyncio.create_task(self._worker_loop(), name="donation-worker")
        self._api_task = asyncio.create_task(self._run_api(), name="control-api")

    async def stop(self) -> None:
        if self._api_server:
            self._api_server.should_exit = True
        if self._api_task:
            self._api_task.cancel()
            try:
                await self._api_task
            except asyncio.CancelledError:
                pass

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        await self._ingestor.stop()
        await self._renderer.stop()
        await self._orchestrator.aclose()

    async def _enqueue_donation(self, event: DonationEvent) -> None:
        await self._donation_queue.put(event)

    async def _worker_loop(self) -> None:
        try:
            while True:
                event = await self._donation_queue.get()
                try:
                    await self._handle_event(event)
                finally:
                    self._donation_queue.task_done()
        except asyncio.CancelledError:  # pragma: no cover
            raise

    async def _handle_event(self, event: DonationEvent) -> None:
        decision = self._gatekeeper.evaluate(event)
        if decision.nsfw:
            task = RenderTask(
                event=event,
                content_type=RenderTaskType.TEXT,
                fallback_text="You are too small",
                nsfw_flag=True,
                hold_duration_sec=self._settings.show_duration_sec,
            )
            await self._render_queue.enqueue(task)
            logger.info("gatekeeper.blocked", extra={"id": event.id, "rule": decision.rule})
            return

        try:
            plan = await self._orchestrator.generate_plan(event)
        except LLMPlanError as exc:
            logger.warning("llm.fallback", extra={"id": event.id, "error": str(exc)})
            fallback_message = "Unable to draw this request"
            task = RenderTask(
                event=event,
                content_type=RenderTaskType.TEXT,
                fallback_text=fallback_message,
                nsfw_flag=False,
                hold_duration_sec=self._settings.show_duration_sec,
            )
            await self._render_queue.enqueue(task)
            return

        if plan.render_text and not plan.steps:
            task = RenderTask(
                event=event,
                content_type=RenderTaskType.TEXT,
                fallback_text=plan.render_text,
                nsfw_flag=False,
                hold_duration_sec=plan.duration_sec or self._settings.show_duration_sec,
            )
        else:
            task = RenderTask(
                event=event,
                content_type=RenderTaskType.PLAN,
                plan=plan,
                nsfw_flag=False,
                hold_duration_sec=plan.duration_sec,
            )

        await self._render_queue.enqueue(task)
        logger.info("queue.enqueued", extra={"id": event.id})

    async def _run_api(self) -> None:
        config = uvicorn.Config(
            self._control.app,
            host=self._settings.api_host,
            port=self._settings.api_port,
            log_level=self._settings.log_level.value.lower(),
            loop="asyncio",
        )
        self._api_server = uvicorn.Server(config)
        await self._api_server.serve()
