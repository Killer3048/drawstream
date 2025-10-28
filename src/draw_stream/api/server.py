"""FastAPI control surface for the renderer pipeline."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import FastAPI, status
from pydantic import BaseModel, Field

from ..config import Settings, get_settings
from ..models import RenderTask
from ..queue import QueueManager
from ..renderer.runtime import RendererRuntime


def _task_to_dict(task: Optional[RenderTask]) -> Optional[Dict[str, Any]]:
    if task is None:
        return None
    event = task.event
    return {
        "id": event.id,
        "donor": event.donor,
        "message": event.message,
        "amount": str(event.amount),
        "currency": event.currency,
        "timestamp": event.timestamp.isoformat(),
        "nsfw": task.nsfw_flag,
        "content_type": task.content_type.value,
    }


class DonationMode(str, Enum):
    MANUAL = "manual"
    DA = "da"


class DonationCommand(BaseModel):
    mode: DonationMode = DonationMode.MANUAL
    amount: Decimal = Field(..., gt=0)
    message: str = Field(..., min_length=1, max_length=2000)
    donor: Optional[str] = Field(default=None, max_length=120)
    currency: Optional[str] = Field(default=None, max_length=8)


CommandHandler = Callable[
    [Decimal, str, DonationMode, Optional[str], Optional[str]], Awaitable[None]
]


class ControlServer:
    """Wraps FastAPI application to expose control endpoints."""

    def __init__(
        self,
        queue: QueueManager,
        renderer: RendererRuntime,
        settings: Optional[Settings] = None,
        command_handler: Optional[CommandHandler] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._queue = queue
        self._renderer = renderer
        self._command_handler = command_handler
        self._shutdown_trigger: Optional[Callable[[], None]] = None
        self._app = FastAPI(title="Draw Stream Control", version="1.0.0")

        @self._app.get("/health", status_code=status.HTTP_200_OK)
        async def health() -> Dict[str, str]:  # noqa: ANN202 - FastAPI response
            return {"status": "ok"}

        @self._app.get("/queue")
        async def queue_state() -> Dict[str, Any]:  # noqa: ANN202 - FastAPI response
            snapshot = self._renderer.snapshot()
            queue_size = await self._queue.size()
            return {
                "active": _task_to_dict(snapshot.active_task),
                "progress": snapshot.progress,
                "hold_remaining_sec": snapshot.hold_remaining,
                "queue_size": queue_size,
                "preview": [_task_to_dict(task) for task in snapshot.queue_preview],
                "fps": snapshot.fps,
            }

        @self._app.post("/queue/skip", status_code=status.HTTP_202_ACCEPTED)
        async def skip_current() -> Dict[str, str]:  # noqa: ANN202 - FastAPI response
            self._renderer.request_skip()
            return {"status": "skip_requested"}

        @self._app.post("/queue/clear", status_code=status.HTTP_202_ACCEPTED)
        async def clear_queue() -> Dict[str, str]:  # noqa: ANN202 - FastAPI response
            await self._queue.clear()
            return {"status": "queue_cleared"}

        @self._app.post("/commands/donate", status_code=status.HTTP_202_ACCEPTED)
        async def enqueue_command(payload: DonationCommand) -> Dict[str, str]:  # noqa: ANN202
            if not self._command_handler:
                return {"status": "handler_unavailable"}
            await self._command_handler(
                payload.amount, payload.message.strip(), payload.mode, payload.donor, payload.currency
            )
            return {"status": "queued"}

        @self._app.post("/control/shutdown", status_code=status.HTTP_202_ACCEPTED)
        async def request_shutdown() -> Dict[str, str]:  # noqa: ANN202
            if self._shutdown_trigger:
                self._shutdown_trigger()
            return {"status": "shutdown_requested"}

    def register_shutdown(self, trigger: Callable[[], None]) -> None:
        self._shutdown_trigger = trigger

    @property
    def app(self) -> FastAPI:
        return self._app

