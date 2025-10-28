"""Scene planning using local LLM."""

from __future__ import annotations

import hashlib
import json
import logging
import random
from pathlib import Path
from typing import Optional

import httpx
from json_repair import repair_json

from ..config import Settings, get_settings
from ..models import DonationEvent, SceneDescription, ScenePlan

logger = logging.getLogger(__name__)

SCENE_SYSTEM_PROMPT = (
    "You are the streamer narrating what will be drawn live in pixel art. Before drawing, evaluate whether the donation is suitable for a PG-13 broadcast. "
    "Reject explicit sexual content, fetish/kink requests, nudity (including topless or genital focus), gore, hate, or harassment. Swimwear, fashionable outfits, and stylised attractive characters (including mentions of body shape like 'curvy' or 'large chest') are fine so long as everyone stays clothed and coverage is similar to modern swimwear. "
    "Respond in JSON with: decision ('draw' or 'reject'), reason (short sentence), fallback_text (what you say to the donor when you refuse), prompt (<=70 words), negative_prompt, style_notes (<=25 words), palette (4-6 hex colors), seed (integer). "
    "Only populate the art fields when decision='draw'. For rejections, give a concise fallback_text in the donor's language and leave prompt/style empty. Never mention streaming, donations, or chat in the art prompt—describe only the scene."
)

FEW_SHOT_EXAMPLES = [
    (
        "Donation summary:\n- donor: NeonWhale\n- amount: 150 USD\n- message: Massive tip! Paint my chrome dragon guitarist on a rain rooftop.",
        json.dumps(
            {
                "decision": "draw",
                "reason": "Dynamic cyberpunk scene",
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
                "decision": "draw",
                "reason": "Wholesome winter scene",
                "prompt": "Cozy timber cabin nestled in deep snow under sweeping aurora curtains, chimney smoke curling upward while a small fox watches from the drift.",
                "negative_prompt": "city skyline, crowds, neon signs",
                "style_notes": "Steady twilight glow with gentle bounce light from the aurora.",
                "palette": ["#0B0D26", "#1E3A8A", "#F5E2B8", "#FF8A5C"],
                "seed": 90210,
            },
            ensure_ascii=False,
        ),
    ),
    (
        "Donation summary:\n- donor: SpicyWolf\n- amount: 60 USD\n- message: Draw my character giving explicit oral sex on stream",
        json.dumps(
            {
                "decision": "reject",
                "reason": "Explicit sexual act violates PG-13 policy",
                "fallback_text": "Спасибо за щедрость, но такие сцены мы на стриме не рисуем—предложите другую идею!",
                "prompt": "",
                "palette": [],
                "seed": 4422,
            },
            ensure_ascii=False,
        ),
    ),
]

MAX_PROMPT_WORDS = 70
MAX_STYLE_WORDS = 25
FALLBACK_VARIANTS = [
    "I don't want to draw that.",
    "Man, that feels wrong to draw.",
    "Are you serious? I can't draw that!",
    "No way, I'm not sketching that.",
    "Hard pass — I'm skipping that idea.",
    "Nope, that crosses my line.",
    "That request feels off; I'm out.",
    "I'm sidestepping that suggestion.",
    "Not touching that one, sorry.",
    "I'm vetoing that drawing.",
    "Can't do that — pick something else.",
    "That vibe is wrong, I refuse.",
    "Nah, that one's not happening.",
    "That's outside my comfort zone.",
    "I have to decline that request.",
    "I'm steering clear of that topic.",
    "That's a no-go for me.",
    "No thanks, choose a different idea.",
]


class _FallbackMessagePicker:
    def __init__(self, phrases: list[str]) -> None:
        self._phrases = list(phrases)
        self._pool: list[str] = []

    def next(self) -> str:
        if not self._pool:
            self._pool = self._phrases.copy()
            random.shuffle(self._pool)
        return self._pool.pop()

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

    async def describe(self, event: DonationEvent) -> ScenePlan:
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
            decision = str(data.get("decision") or "draw").lower()
            approved = decision == "draw"
            reason = data.get("reason") or None
            fallback_text = data.get("fallback_text") or reason

            description = None
            if approved:
                palette = [color for color in data.get("palette", []) if isinstance(color, str)]
                palette = [color.upper() for color in palette[:6]]
                prompt = self._clip_words(data.get("prompt", event.message), MAX_PROMPT_WORDS)
                style_notes = self._clip_words(data.get("style_notes", ""), MAX_STYLE_WORDS)
                seed = data.get("seed")
                if not isinstance(seed, int):
                    seed = self._fallback_seed(event)
                description = SceneDescription(
                    prompt=prompt,
                    negative_prompt=data.get("negative_prompt"),
                    style_notes=style_notes or None,
                    palette=palette,
                    seed=seed,
                )

            rejection_text = None
            if not approved:
                rejection_text = _fallback_picker.next()

            return ScenePlan(
                approved=approved,
                description=description,
                fallback_text=rejection_text,
                reason=reason,
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
_fallback_picker = _FallbackMessagePicker(FALLBACK_VARIANTS)
