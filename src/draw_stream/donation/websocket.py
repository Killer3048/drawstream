"""Donation Alerts WebSocket ingestion via Centrifugo."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import websockets
from websockets.client import WebSocketClientProtocol

from ..config import Settings, get_settings
from ..models import DonationEvent

logger = logging.getLogger(__name__)


class DonationAlertsWebSocket:
    """Handles Centrifugo WebSocket subscription for donation events."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._backoff_base = 2
        self._backoff_max = 60

    async def listen(self) -> AsyncIterator[DonationEvent]:
        """Yield donation events as they arrive via WebSocket."""

        backoff = 1
        while True:
            try:
                async for event in self._run_once():
                    backoff = 1
                    yield event
            except Exception as exc:  # pragma: no cover - network failures
                logger.warning("ws.connection_error", extra={"error": str(exc)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * self._backoff_base, self._backoff_max)

    async def _run_once(self) -> AsyncIterator[DonationEvent]:
        headers = {
            "Authorization": f"Bearer {self._settings.da_access_token.get_secret_value()}",
            "Accept": "application/json",
        }

        channel = self._channel_name()
        ws_url = self._ws_url()
        async with websockets.connect(ws_url, additional_headers=headers) as ws:
            await self._send_subscribe(ws, channel)
            async for raw in ws:
                event = self._parse_event(raw)
                if event:
                    yield event

    async def _send_subscribe(self, ws: WebSocketClientProtocol, channel: str) -> None:
        payload = {
            "command": "subscribe",
            "params": {"channels": [channel]},
        }
        await ws.send(json.dumps(payload))

    def _channel_name(self) -> str:
        user_id = self._settings.da_user_id
        if not user_id:
            raise RuntimeError("DA_USER_ID must be set for WebSocket subscriptions")
        return f"$alerts:donation_{user_id}"

    def _parse_event(self, raw: str) -> Optional[DonationEvent]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("ws.invalid_json", extra={"raw": raw[:100]})
            return None

        data = payload.get("data") or {}
        if "data" in data:
            data = data["data"]

        try:
            return DonationEvent(
                id=str(data["id"]),
                donor=data.get("username") or data.get("name") or data.get("nickname"),
                message=data.get("message") or "",
                amount=Decimal(str(data.get("amount_main") or data.get("amount") or 0)),
                currency=data.get("currency") or data.get("currency_code") or "USD",
                timestamp=self._parse_timestamp(data.get("created_at") or data.get("date_created")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("ws.event_parse_error", extra={"error": str(exc)})
            return None

    @staticmethod
    def _parse_timestamp(raw: Optional[str]) -> datetime:
        if not raw:
            return datetime.now(timezone.utc)
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    def _ws_url(self) -> str:
        raw = str(self._settings.da_ws_url)
        if raw.startswith("https://"):
            return "wss://" + raw[len("https://") :]
        if raw.startswith("http://"):
            return "ws://" + raw[len("http://") :]
        return raw
