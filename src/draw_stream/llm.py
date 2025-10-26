"""Compatibility wrapper around the new art pipeline."""

from __future__ import annotations

from .models import DonationEvent
from .artistry.pipeline import ArtPipeline, ArtPipelineError


class LLMPlanError(RuntimeError):
    """Kept for backwards compatibility with previous pipeline."""


class LLMOrchestrator:
    """Legacy orchestrator interface delegating to ArtPipeline."""

    def __init__(self, *_, **__) -> None:
        self._pipeline = ArtPipeline()

    async def aclose(self) -> None:
        await self._pipeline.aclose()

    async def generate_plan(self, event: DonationEvent):
        try:
            return await self._pipeline.create_plan(event)
        except ArtPipelineError as exc:  # pragma: no cover - thin wrapper
            raise LLMPlanError(str(exc)) from exc
