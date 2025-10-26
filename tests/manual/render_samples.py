"""Generate sample Canvas-DSL renders and export them as PNG images."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src"))

import pygame  # noqa: E402

from draw_stream.config import get_settings  # noqa: E402
# Diagnostics/VRAM helpers
from subprocess import run

from draw_stream.llm import LLMOrchestrator  # noqa: E402
from draw_stream.models import DonationEvent  # noqa: E402
from draw_stream.renderer.animations import StepPreparer  # noqa: E402
from draw_stream.renderer.surface import create_canvas, hex_to_rgb, upscale  # noqa: E402


SAMPLES = [
    "Draw an isometric cyberpunk dragon playing a neon guitar on a rainy rooftop with city lights behind.",
    "Draw a cozy pixel art cabin in snowy forest with smoke from chimney and aurora sky.",
    "Create a cheerful donut-shaped robot serving coffee to tiny cats in a pastel pixel cafe.",
]

OUTPUT_DIR = Path("out/render_samples")
OLLAMA_MODEL = "qwen2.5-coder:14b-instruct-q4_K_M"


async def generate_plan(orchestrator: LLMOrchestrator, message: str) -> tuple[str, str, pygame.Surface]:
    """Return (filename, caption, surface) tuple for given donation message."""

    event = DonationEvent(
        id=message[:32],
        donor="Sample",
        message=message,
        amount="5.00",
        currency="USD",
        timestamp="2024-01-01T00:00:00+00:00",
    )

    plan = await orchestrator.generate_plan(event)
    canvas_color = hex_to_rgb(plan.canvas.bg)
    base_surface = create_canvas(plan.canvas.w, plan.canvas.h, canvas_color)

    if plan.steps:
        preparer = StepPreparer(plan.canvas, get_settings().default_step_duration_ms)
        for step in plan.steps:
            for prepared in preparer.prepare(step):
                prepared.apply_final(base_surface)
    elif plan.render_text:
        # Basic fallback card
        font = pygame.font.SysFont("arial", 14, bold=True)
        text_surface = font.render(plan.render_text, True, hex_to_rgb("#FFFFFF"))
        rect = text_surface.get_rect(center=(plan.canvas.w // 2, plan.canvas.h // 2))
        base_surface.blit(text_surface, rect)

    window_scale = get_settings().window_scale
    upscaled = upscale(base_surface, window_scale)
    safe_name = "".join(ch for ch in message[:40] if ch.isalnum() or ch in (" ", "-", "_")).strip().replace(" ", "_")
    filename = f"{safe_name or 'sample'}.png"
    return filename, plan.caption, upscaled


async def main() -> None:
    clear_vram()
    pygame.init()
    pygame.font.init()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    orchestrator = LLMOrchestrator()
    try:
        for message in SAMPLES:
            try:
                filename, caption, surface = await generate_plan(orchestrator, message)
            except Exception as exc:  # pragma: no cover - manual inspection tool
                print(f"Failed to render '{message}': {exc}")
                continue

            path = OUTPUT_DIR / filename
            pygame.image.save(surface, path.as_posix())
            print(f"Saved {path} (caption: {caption})")
    finally:
        await orchestrator.aclose()
        pygame.quit()


def clear_vram() -> None:
    try:
        run(["ollama", "stop", OLLAMA_MODEL], check=False)
    except FileNotFoundError:
        pass
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
