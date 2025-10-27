"""Donation ingestion coordinator."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Awaitable, Callable, Deque, Optional, Set

from ..config import Settings, get_settings
from ..models import DonationEvent
from .rest import DonationAlertsRESTClient
from .websocket import DonationAlertsWebSocket

logger = logging.getLogger(__name__)


EventCallback = Callable[[DonationEvent], Awaitable[None]]


class DonationIngestor:
    """Coordinates WebSocket ingestion with REST fallback."""

    def __init__(self, callback: EventCallback, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._callback = callback
        self._ws_client = DonationAlertsWebSocket(self._settings)
        self._rest_client = DonationAlertsRESTClient(self._settings)
        self._stop_event = asyncio.Event()
        self._ws_task: Optional[asyncio.Task[None]] = None
        self._rest_task: Optional[asyncio.Task[None]] = None
        self._seen_ids: Deque[str] = deque(maxlen=256)
        self._start_time = datetime.now(timezone.utc)

    async def start(self) -> None:
        logger.info("ingestor.starting")
        self._ws_task = asyncio.create_task(self._run_ws(), name="donation-ws")
        self._rest_task = asyncio.create_task(self._run_rest(), name="donation-rest")

    async def stop(self) -> None:
        logger.info("ingestor.stopping")
        self._stop_event.set()
        tasks = [t for t in (self._ws_task, self._rest_task) if t]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._rest_client.aclose()
        logger.info("ingestor.stopped")

    async def _run_ws(self) -> None:
        try:
            async for event in self._ws_client.listen():
                if self._stop_event.is_set():
                    break
                if not self._should_ignore(event) and self._dedupe(event.id):
                    await self._callback(event)
        except asyncio.CancelledError:  # pragma: no cover - cancellation path
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("ingestor.ws_failure", exc_info=exc)

    async def _run_rest(self) -> None:
        interval = self._settings.da_rest_poll_interval_sec
        try:
            while not self._stop_event.is_set():
                try:
                    events = await self._rest_client.fetch_latest(limit=10)
                except Exception as exc:  # pragma: no cover - network failure
                    logger.warning("ingestor.rest_error", extra={"error": str(exc)})
                else:
                    for event in events:
                        if not self._should_ignore(event) and self._dedupe(event.id):
                            await self._callback(event)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:  # pragma: no cover - cancellation path
            raise

    def _dedupe(self, event_id: str) -> bool:
        if event_id in self._seen_ids:
            return False
        self._seen_ids.append(event_id)
        return True

    def _should_ignore(self, event: DonationEvent) -> bool:
        # skip historical donations (e.g., REST returns previous entries on startup)
        if event.timestamp.tzinfo is None:
            event_ts = event.timestamp.replace(tzinfo=timezone.utc)
        else:
            event_ts = event.timestamp.astimezone(timezone.utc)
        return event_ts < self._start_time
