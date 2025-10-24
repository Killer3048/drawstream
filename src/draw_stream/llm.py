"""LLM orchestration for Canvas DSL generation."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from .canvas_dsl import CanvasDocument, ensure_canvas_document
from .config import Settings, get_settings
from .models import DonationEvent

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You convert live stream donation requests into a pixel art drawing plan. "
    "Return ONLY valid JSON that adheres to the Canvas-DSL schema. "
    "Use a 96x96 canvas unless the user explicitly requests another size. "
    "Limit the palette to simple hex colors suitable for pixel art. "
    "Every plan must include the caption 'All for you'. "
    "If the request cannot be satisfied, respond with a render_text directive explaining why."
)


class LLMPlanError(RuntimeError):
    """Raised when the LLM orchestrator cannot produce a usable plan."""


class LLMOrchestrator:
    """Handles communication with the local LLM backend."""

    def __init__(self, settings: Optional[Settings] = None, client: Optional[httpx.AsyncClient] = None) -> None:
        self._settings = settings or get_settings()
        timeout = httpx.Timeout(self._settings.llm_timeout_sec)
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate_plan(self, event: DonationEvent) -> CanvasDocument:
        """Generate a Canvas DSL plan for the provided donation event."""

        payload = {
            "model": self._settings.llm_model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Donor message: " + event.message + "\n"
                        f"Donor name: {event.donor or 'anonymous'}\n"
                        f"Amount: {event.amount} {event.currency}"
                    ),
                },
            ],
            "temperature": self._settings.llm_temperature,
            "max_tokens": self._settings.llm_max_tokens,
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None
        attempts = self._settings.llm_retry_attempts + 1
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.post(
                    str(self._settings.llm_endpoint),
                    json=payload,
                    headers=self._settings.llm_headers,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "llm.request_failed",
                    extra={"attempt": attempt, "error": str(exc)},
                )
                continue

            try:
                content = response.json()
            except json.JSONDecodeError as exc:  # pragma: no cover - httpx should give dict already
                last_error = exc
                logger.warning("llm.invalid_json", extra={"attempt": attempt})
                continue

            choice = self._extract_choice(content)
            if choice is None:
                last_error = LLMPlanError("Response missing choices")
                logger.warning("llm.missing_choice", extra={"attempt": attempt})
                continue

            try:
                plan_dict = json.loads(choice)
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.warning("llm.choice_not_json", extra={"attempt": attempt, "snippet": choice[:100]})
                continue

            try:
                document = ensure_canvas_document(plan_dict)
            except ValueError as exc:
                last_error = exc
                logger.warning("llm.plan_validation_failed", extra={"attempt": attempt})
                continue

            logger.info(
                "llm.plan_success",
                extra={"attempt": attempt, "version": document.version},
            )
            return document

        raise LLMPlanError("Failed to generate Canvas plan") from last_error

    @staticmethod
    def _extract_choice(payload: Any) -> Optional[str]:
        try:
            choices = payload["choices"]
            first = choices[0]
            message = first["message"]
            return message["content"]
        except (KeyError, IndexError, TypeError):  # pragma: no cover - defensive
            return None

