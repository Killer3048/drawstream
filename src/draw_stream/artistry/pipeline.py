"""Full artistic pipeline: scene planning -> pixel generation -> Canvas DSL."""

from __future__ import annotations

import logging
import subprocess

from ..config import LLMBackend, get_settings
from ..models import DonationEvent, SceneDescription
from .image_to_canvas import ImageToCanvas
from .pixel_generator import PixelArtGenerator, PixelArtGeneratorError
from .scene_planner import ScenePlanner, ScenePlannerError

logger = logging.getLogger(__name__)


class ArtPipelineError(RuntimeError):
    """Raised when the art pipeline fails."""


class ArtPipeline:
    """Coordinates scene planning, pixel generation, and Canvas DSL building."""

    def __init__(
        self,
        scene_planner: ScenePlanner | None = None,
        pixel_generator: PixelArtGenerator | None = None,
        canvas_builder: ImageToCanvas | None = None,
    ) -> None:
        self._settings = get_settings()
        self._scene_planner = scene_planner or ScenePlanner()
        self._pixel_generator = pixel_generator or PixelArtGenerator()
        self._canvas_builder = canvas_builder or ImageToCanvas()

    async def create_plan(self, event: DonationEvent):
        try:
            scene = await self._scene_planner.describe(event)
            logger.info("scene.planned", extra={"id": event.id})
        except ScenePlannerError as exc:
            logger.warning("scene.fallback", extra={"id": event.id, "error": str(exc)})
            scene = self._fallback_scene(event)

        self._free_llm_vram()

        try:
            image = await self._pixel_generator.generate(scene)
        except PixelArtGeneratorError as exc:
            raise ArtPipelineError("Pixel art generation failed") from exc

        try:
            document = self._canvas_builder.build(image)
        except Exception as exc:  # pragma: no cover
            raise ArtPipelineError("Canvas conversion failed") from exc

        return document

    async def aclose(self) -> None:
        await self._scene_planner.aclose()

    def _fallback_scene(self, event: DonationEvent):
        from ..models import SceneDescription

        prompt = (
            f"Pixel art illustration of: {event.message}. "
            "Add cohesive palette, playful lighting, crisp outlines."
        )
        return SceneDescription(prompt=prompt, palette=[])

    def _free_llm_vram(self) -> None:
        settings = self._settings
        if settings.llm_backend == LLMBackend.OLLAMA:
            try:
                subprocess.run(["ollama", "stop", settings.llm_model_id], check=False)
            except FileNotFoundError:  # pragma: no cover - optional dependency
                pass

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # pragma: no cover - defensive: torch missing or misconfigured
            pass
