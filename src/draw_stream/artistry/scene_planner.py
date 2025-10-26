"""Scene planning using local LLM."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import httpx
from json_repair import repair_json

from ..config import Settings, get_settings
from ..models import DonationEvent, SceneDescription

logger = logging.getLogger(__name__)

SCENE_SYSTEM_PROMPT = (
    "You are the streamer narrating what will be drawn live in pixel art. "
    "Interpret each donation like a director's brief: extract the main subjects, camera, mood, and palette cues. "
    "Keep the `prompt` punchy (<=70 words), written in present tense, and mention perspective + scale. "
    "Output strict JSON with keys: prompt, negative_prompt, style_notes (<=25 words), palette (4-6 hex colors), seed (integer). "
    "If the donor forgot details, invent tasteful ones that fit the request. "
    "Never mention streaming, donations, or chat inside the prompt—describe only the scene."
)

FEW_SHOT_EXAMPLES = [
    (
        "Donation summary:\n- donor: NeonWhale\n- amount: 150 USD\n- message: Massive tip! Paint my chrome dragon guitarist on a rain rooftop.",
        json.dumps(
            {
                "prompt": "Isometric neon rooftop with a chrome dragon shredding a glowing guitar, rain streaking across a holographic skyline and drones circling above.",
                "negative_prompt": "daylight, soft pastel sky, medieval castles",
                "style_notes": "Dark stormy night, harsh rim light and puddle reflections.",
                "palette": ["#12F28F", "#0AB5FF", "#FF2E88", "#05060A"],
                "seed": 421337,
            },
            ensure_ascii=False,
        ),
    ),
    (
        "Donation summary:\n- donor: CozyFox\n- amount: 25 USD\n- message: Could you paint a snowy cabin with aurora and a curious fox?",
        json.dumps(
            {
                "prompt": "Cozy timber cabin nestled in deep snow under sweeping aurora curtains, chimney smoke curling upward while a small fox watches from the drift.",
                "negative_prompt": "city skyline, crowds, neon signs",
                "style_notes": "Steady twilight glow with gentle bounce light from the aurora.",
                "palette": ["#0B0D26", "#1E3A8A", "#F5E2B8", "#FF8A5C"],
                "seed": 90210,
            },
            ensure_ascii=False,
        ),
    ),
]

MAX_PROMPT_WORDS = 70
MAX_STYLE_WORDS = 25

ASSETS_PATH = Path(__file__).resolve().parents[1] / "assets" / "examples" / "aurora_cabin_plan.json"
try:
    EXAMPLE_PLAN = ASSETS_PATH.read_text(encoding="utf-8")
except FileNotFoundError:  # pragma: no cover - optional asset
    EXAMPLE_PLAN = "{\"version\": \"1.0\", \"caption\": \"All for you\"}"


class ScenePlannerError(RuntimeError):
    """Raised when scene planning fails."""


class ScenePlanner:
    """LLM-powered scene description generator."""

    def __init__(self, settings: Optional[Settings] = None, client: Optional[httpx.AsyncClient] = None) -> None:
        self._settings = settings or get_settings()
        timeout = httpx.Timeout(self._settings.llm_timeout_sec)
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def describe(self, event: DonationEvent) -> SceneDescription:
        messages = [
            {"role": "system", "content": SCENE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Reference Canvas-DSL plan for inspiration:\n" + EXAMPLE_PLAN,
            },
        ]
        for user_sample, assistant_json in FEW_SHOT_EXAMPLES:
            messages.append({"role": "user", "content": user_sample})
            messages.append({"role": "assistant", "content": assistant_json})

        messages.append({"role": "user", "content": self._format_event_summary(event)})

        payload = {
            "model": self._settings.llm_model_id,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": min(512, self._settings.llm_max_tokens),
            "response_format": {"type": "json_object"},
        }

        try:
            response = await self._client.post(
                str(self._settings.llm_endpoint),
                json=payload,
                headers=self._settings.llm_headers,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure
            raise ScenePlannerError("Scene planner request failed") from exc

        content = response.json()
        choice = self._extract_choice(content)
        if not choice:
            raise ScenePlannerError("Scene planner returned empty content")

        try:
            data = json.loads(choice)
        except json.JSONDecodeError:
            try:
                data = json.loads(repair_json(choice))
            except Exception as exc:  # pragma: no cover
                raise ScenePlannerError("Scene planner JSON invalid") from exc

        try:
            palette = [color for color in data.get("palette", []) if isinstance(color, str)]
            palette = [color.upper() for color in palette[:6]]
            prompt = self._clip_words(data.get("prompt", event.message), MAX_PROMPT_WORDS)
            style_notes = self._clip_words(data.get("style_notes", ""), MAX_STYLE_WORDS)
            seed = data.get("seed")
            if not isinstance(seed, int):
                seed = self._fallback_seed(event)
            return SceneDescription(
                prompt=prompt,
                negative_prompt=data.get("negative_prompt"),
                style_notes=style_notes or None,
                palette=palette,
                seed=seed,
            )
        except Exception as exc:  # pragma: no cover
            raise ScenePlannerError("Scene planner response malformed") from exc

    @staticmethod
    def _extract_choice(payload: dict) -> Optional[str]:
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _clip_words(text: str, limit: int) -> str:
        words = (text or "").split()
        if len(words) <= limit:
            return (text or "").strip()
        return " ".join(words[:limit]).strip()

    @staticmethod
    def _format_event_summary(event: DonationEvent) -> str:
        donor = event.donor or "anonymous"
        summary = [
            "Donation summary:",
            f"- donor: {donor}",
            f"- amount: {event.amount} {event.currency}",
            f"- message: {event.message}",
        ]
        return "\n".join(summary)

    @staticmethod
    def _fallback_seed(event: DonationEvent) -> int:
        base = f"{event.id}:{event.timestamp.isoformat()}".encode("utf-8", "ignore")
        digest = hashlib.sha256(base).hexdigest()
        return int(digest[:8], 16)
