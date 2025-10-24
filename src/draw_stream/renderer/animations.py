"""Step animation helpers for the renderer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pygame

from ..canvas_dsl import (
    AnimationConfig,
    CanvasSpec,
    CircleStep,
    LineStep,
    PixelsStep,
    PolygonStep,
    RectStep,
    StepGroup,
    TextStep,
    CanvasStep,
)
from .surface import create_canvas, hex_to_rgb


@dataclass(slots=True)
class StepTimeline:
    """Timing metadata for a single step."""

    duration_ms: int
    delay_ms: int
    mode: str


@dataclass(slots=True)
class PreparedStep:
    """Prepared renderer step with static surface and metadata."""

    step: CanvasStep
    surface: pygame.Surface
    timeline: StepTimeline
    points: list[tuple[int, int]]

    def render(self, target: pygame.Surface, progress: float) -> None:
        progress = max(0.0, min(1.0, progress))

        if isinstance(self.step, PixelsStep) and self.timeline.mode == "pixel_reveal":
            total = len(self.points)
            count = max(1, int(total * progress))
            color = hex_to_rgb(self.step.color)
            for x, y in self.points[:count]:
                target.set_at((x, y), color)
            return

        temp = self.surface.copy()
        alpha = int(255 * progress)
        temp.set_alpha(alpha)
        target.blit(temp, (0, 0))

    def apply_final(self, target: pygame.Surface) -> None:
        if isinstance(self.step, PixelsStep) and self.timeline.mode == "pixel_reveal":
            color = hex_to_rgb(self.step.color)
            for x, y in self.points:
                target.set_at((x, y), color)
        else:
            target.blit(self.surface, (0, 0))


class StepPreparer:
    """Convert Canvas DSL steps into pygame surfaces and metadata."""

    def __init__(self, canvas: CanvasSpec, default_duration_ms: int) -> None:
        self._canvas = canvas
        self._default_duration_ms = default_duration_ms

    def prepare(self, step: CanvasStep) -> list[PreparedStep]:
        if isinstance(step, StepGroup):
            prepared: list[PreparedStep] = []
            for nested in step.steps:
                prepared.extend(self.prepare(nested))
            return prepared
        return [self._prepare_leaf(step)]

    def _prepare_leaf(self, step: CanvasStep) -> PreparedStep:
        surface = create_canvas(self._canvas.w, self._canvas.h)
        points: list[tuple[int, int]] = []

        if isinstance(step, RectStep):
            rect = pygame.Rect(step.x, step.y, step.w, step.h)
            if step.fill:
                pygame.draw.rect(surface, hex_to_rgb(step.fill), rect)
            if step.outline:
                pygame.draw.rect(surface, hex_to_rgb(step.outline), rect, width=1)
        elif isinstance(step, CircleStep):
            color_fill = hex_to_rgb(step.fill) if step.fill else None
            color_outline = hex_to_rgb(step.outline) if step.outline else None
            if color_fill:
                pygame.draw.circle(surface, color_fill, (step.cx, step.cy), step.r)
            if color_outline:
                pygame.draw.circle(surface, color_outline, (step.cx, step.cy), step.r, width=1)
        elif isinstance(step, LineStep):
            pygame.draw.line(surface, hex_to_rgb(step.color), (step.x1, step.y1), (step.x2, step.y2), step.width)
        elif isinstance(step, PolygonStep):
            if step.fill:
                pygame.draw.polygon(surface, hex_to_rgb(step.fill), step.points)
            if step.outline:
                pygame.draw.polygon(surface, hex_to_rgb(step.outline), step.points, width=1)
        elif isinstance(step, PixelsStep):
            points = list(step.points)
            for x, y in points:
                surface.set_at((x, y), hex_to_rgb(step.color))
        elif isinstance(step, TextStep):
            font = pygame.font.SysFont(step.font or "monospace", step.size)
            text_surface = font.render(step.value, True, hex_to_rgb(step.color))
            surface.blit(text_surface, (step.x, step.y))
        else:  # pragma: no cover - future proofing
            raise ValueError(f"Unsupported step type: {type(step)}")

        timeline = self._build_timeline(step)
        return PreparedStep(step=step, surface=surface, timeline=timeline, points=points)

    def _build_timeline(self, step: CanvasStep) -> StepTimeline:
        animate: Optional[AnimationConfig] = getattr(step, "animate", None)
        duration = self._default_duration_ms
        delay = 0
        mode = "fill"
        if animate:
            if animate.duration_ms:
                duration = animate.duration_ms
            if animate.delay_ms:
                delay = animate.delay_ms
            if animate.mode:
                mode = animate.mode
        return StepTimeline(duration_ms=duration, delay_ms=delay, mode=mode)

