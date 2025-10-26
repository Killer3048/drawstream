"""Probe the ScenePlanner with varied donation messages and store responses."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src"))

from draw_stream.artistry.scene_planner import ScenePlanner  # noqa: E402
from draw_stream.models import DonationEvent  # noqa: E402

OUTPUT_DIR = Path("out/scene_planner_probe")
SAMPLES = [
    ("simple_cat", "Draw my calico cat wearing headphones chilling on a beanbag"),
    ("city_chase", "Mega request: chase scene on the rooftops of Neo-Kyoto with two couriers on hoverboards"),
    ("deep_sea", "Please paint a bioluminescent jellyfish orchestra in deep ocean darkness"),
    ("mech_garden", "Garden gnomes tending bonsai-sized mechs at sunrise"),
    ("retro_arcade", "Retro arcade battle between two pinball wizards inside the machine"),
    ("starship_kitchen", "Chef cooking ramen in zero gravity aboard a starship galley"),
    ("desert_train", "Steam train crossing a candy-colored desert canyon at dusk"),
    ("festival_drums", "Taiko drum line of tanukis celebrating a lantern festival"),
    ("skywhale", "Gigantic sky-whale delivering letters to floating islands"),
    ("witch_market", "Late-night witch market lit only by potions under a crescent moon"),
]


def make_event(slug: str, message: str) -> DonationEvent:
    return DonationEvent(
        id=slug,
        donor="LLM QA",
        message=message,
        amount="13.37",
        currency="USD",
        timestamp="2024-01-01T00:00:00+00:00",
    )


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    planner = ScenePlanner()
    try:
        for slug, message in SAMPLES:
            scene = await planner.describe(make_event(slug, message))
            path = OUTPUT_DIR / f"{slug}.json"
            path.write_text(scene.model_dump_json(indent=2, ensure_ascii=False))
            print(f"{slug}: prompt_words={len(scene.prompt.split())} palette={len(scene.palette)} seed={scene.seed}")
    finally:
        await planner.aclose()


if __name__ == "__main__":
    asyncio.run(main())
