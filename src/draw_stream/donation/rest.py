"""Donation Alerts REST polling client."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Optional

import httpx

from ..config import Settings, get_settings
from ..models import DonationEvent


def _parse_timestamp(raw: str) -> datetime:
    ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


class DonationAlertsRESTClient:
    """Lightweight wrapper around the Donation Alerts REST endpoints."""

    def __init__(self, settings: Optional[Settings] = None, client: Optional[httpx.AsyncClient] = None) -> None:
        self._settings = settings or get_settings()
        headers = {
            "Authorization": f"Bearer {self._settings.da_access_token.get_secret_value()}",
            "Accept": "application/json",
        }
        self._client = client or httpx.AsyncClient(base_url=str(self._settings.da_api_base), headers=headers)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_latest(self, limit: int = 10) -> Iterable[DonationEvent]:
        response = await self._client.get("/donations", params={"limit": limit})
        response.raise_for_status()

        payload = response.json()
        data = payload.get("data", [])

        events: list[DonationEvent] = []
        for item in data:
            try:
                events.append(self._normalize_item(item))
            except (KeyError, ValueError, TypeError):
                continue
        return events

    def _normalize_item(self, item: dict) -> DonationEvent:
        donor = item.get("username") or item.get("name") or item.get("nickname")
        amount_val = item.get("amount_main") or item.get("amount") or 0
        amount = Decimal(str(amount_val))
        currency = item.get("currency") or item.get("currency_code") or "USD"
        message = item.get("message") or ""
        timestamp_raw = item.get("created_at") or item.get("date_created")
        if not timestamp_raw:
            raise ValueError("Missing timestamp")
        timestamp = _parse_timestamp(timestamp_raw)
        return DonationEvent(
            id=str(item.get("id")),
            donor=donor,
            message=message,
            amount=amount,
            currency=currency,
            timestamp=timestamp,
        )

