"""LLM orchestration for Canvas DSL generation."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx
from json_repair import repair_json

from pathlib import Path

from .canvas_dsl import CanvasDocument, ensure_canvas_document
from .config import Settings, get_settings
from .models import DonationEvent

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a deterministic Canvas-DSL planner. "
    "Always reply with a single JSON object using only these top-level keys: "
    "version, canvas, palette, steps, caption, seed, render_text, duration_sec. "
    "Omit optional keys instead of leaving them null. "
    "Use version \"1.0\". "
    "The canvas object must include integer fields w, h, bg. Default to 96 and background '#202020'. "
    "Every step object must include op and the correct fields for that primitive. "
    "rect requires x,y,w,h and may include fill and outline (use fill instead of color). "
    "circle requires cx,cy,r with optional fill and outline. "
    "line requires x1,y1,x2,y2,width,color. "
    "polygon requires points as an array of [x,y] pairs plus optional fill/outline. "
    "pixels requires points as an array of [x,y] pairs and a color field. "
    "text requires x,y,value and may include font,size,color. "
    "group requires a nested steps array. "
    "For safe requests you MUST include a non-empty steps array and you MUST NOT include render_text. "
    "Assume all donor requests are safe unless they explicitly contain NSFW content. "
    "Limit the number of steps to 20 and keep each points list to 32 coordinates or fewer. "
    "Use double-quoted hex colours like '#AABBCC'. "
    "Ensure caption is exactly 'All for you'. "
    "Do not include comments, trailing commas, or narrative text. "
    "If the request cannot be fulfilled safely, output only render_text='You are too small', caption and canvas, "
    "and omit steps. "
    "Example output for reference:\n"
    "{\n"
    "  \"version\": \"1.0\",\n"
    "  \"canvas\": {\"w\": 96, \"h\": 96, \"bg\": \"#1A1A1A\"},\n"
    "  \"caption\": \"All for you\",\n"
    "  \"palette\": [\"#FFD93D\", \"#FFE066\", \"#FFFFFF\", \"#9B5DE5\", \"#F15BB5\"],\n"
    "  \"steps\": [\n"
    "    {\"op\": \"pixels\", \"color\": \"#FFD93D\", \"points\": [[45,20],[46,20],[47,20],[48,20],[49,20]]},\n"
    "    {\"op\": \"pixels\", \"color\": \"#FFD93D\", \"points\": [[44,21],[45,21],[46,21],[47,21],[48,21],[49,21],[50,21]]},\n"
    "    {\"op\": \"pixels\", \"color\": \"#FFE066\", \"points\": [[42,34],[52,34],[41,35],[53,35]]},\n"
    "    {\"op\": \"rect\", \"x\": 40, \"y\": 42, \"w\": 4, \"h\": 6, \"fill\": \"#FFFFFF\"},\n"
    "    {\"op\": \"rect\", \"x\": 52, \"y\": 42, \"w\": 4, \"h\": 6, \"fill\": \"#FFFFFF\"},\n"
    "    {\"op\": \"pixels\", \"color\": \"#9B5DE5\", \"points\": [[46,46],[47,46],[48,46]]},\n"
    "    {\"op\": \"pixels\", \"color\": \"#F15BB5\", \"points\": [[44,55],[45,56],[46,57],[47,56],[48,55]]},\n"
    "    {\"op\": \"rect\", \"x\": 30, \"y\": 60, \"w\": 36, \"h\": 4, \"fill\": \"#FFE066\"}\n"
    "  ]\n"
    "}"
)

CANVAS_JSON_SCHEMA = {
    "name": "CanvasPlan",
    "schema": {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "canvas": {
                "type": "object",
                "properties": {
                    "w": {"type": "integer"},
                    "h": {"type": "integer"},
                    "bg": {"type": "string"}
                },
                "required": ["w", "h", "bg"],
                "additionalProperties": True,
            },
            "caption": {"type": "string"},
            "palette": {
                "type": "array",
                "items": {"type": "string"}
            },
            "seed": {"type": "integer"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {
                            "type": "string",
                            "enum": [
                                "rect",
                                "circle",
                                "line",
                                "polygon",
                                "pixels",
                                "text",
                                "group"
                            ],
                        }
                    },
                    "required": ["op"],
                    "additionalProperties": True,
                }
            },
            "render_text": {"type": "string"},
            "duration_sec": {"type": "integer"}
        },
        "required": ["version", "canvas", "caption"],
        "additionalProperties": False,
    },
}


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
                        "Reference example: here is a full Canvas-DSL plan for an aurora cabin scene."
                    ),
                },
                {"role": "assistant", "content": EXAMPLE_PLAN_JSON},
                {
                    "role": "user",
                    "content": (
                        "Donor message: " + event.message + "\n"
                        f"Donor name: {event.donor or 'anonymous'}\n"
                        f"Amount: {event.amount} {event.currency}\n"
                        "Produce Canvas-DSL steps that draw this scene."
                    ),
                },
            ],
            "temperature": self._settings.llm_temperature,
            "max_tokens": self._settings.llm_max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": CANVAS_JSON_SCHEMA,
            },
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
                try:
                    repaired = repair_json(choice)
                    plan_dict = json.loads(repaired)
                    logger.info(
                        "llm.choice_repaired",
                        extra={"attempt": attempt},
                    )
                except Exception as repair_exc:  # pragma: no cover - repair failure
                    last_error = repair_exc
                    logger.warning(
                        "llm.choice_not_json",
                        extra={"attempt": attempt, "snippet": choice[:100]},
                    )
                    continue

            if isinstance(plan_dict, dict):
                plan_dict.setdefault("version", "1.0")
                plan_dict.setdefault("caption", "All for you")
                canvas = plan_dict.get("canvas")
                if isinstance(canvas, dict):
                    canvas.setdefault("w", self._settings.canvas_w)
                    canvas.setdefault("h", self._settings.canvas_h)
                    canvas.setdefault("bg", "#202020")

                if not plan_dict.get("render_text"):
                    plan_dict.pop("render_text", None)

                if "steps" not in plan_dict and "render_text" not in plan_dict:
                    plan_dict["render_text"] = "You are too small"

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
EXAMPLE_PLAN_PATH = Path(__file__).resolve().parents[1] / "assets" / "examples" / "aurora_cabin_plan.json"
try:
    EXAMPLE_PLAN_JSON = EXAMPLE_PLAN_PATH.read_text(encoding="utf-8")
except FileNotFoundError:  # pragma: no cover - optional asset
    EXAMPLE_PLAN_JSON = "{\"version\": \"1.0\", \"caption\": \"All for you\"}"
