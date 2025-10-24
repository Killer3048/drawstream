"""Heads-up display rendering for the stream window."""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import wrap
from typing import Sequence

import pygame

from ..models import RenderTask
from .surface import hex_to_rgb


@dataclass(slots=True)
class HUDState:
    active_task: RenderTask | None
    progress: float
    hold_remaining: float
    hold_total: float
    queue_preview: Sequence[RenderTask]
    caption: str
    fps: float


class HudRenderer:
    def __init__(self, window_size: tuple[int, int]) -> None:
        width, _ = window_size
        base_size = max(16, width // 40)
        self._title_font = pygame.font.SysFont("arial", base_size + 4, bold=True)
        self._body_font = pygame.font.SysFont("arial", base_size)
        self._small_font = pygame.font.SysFont("arial", base_size - 4)
        self._fg = hex_to_rgb("#FFFFFF")
        self._accent = hex_to_rgb("#66CCFF")
        self._warning = hex_to_rgb("#FF6666")

    def draw(self, surface: pygame.Surface, state: HUDState) -> None:
        width, height = surface.get_size()
        padding = 20

        self._draw_active(surface, state, padding, width // 2 - padding)
        self._draw_queue(surface, state.queue_preview, width // 2 + padding, padding, width - padding)
        self._draw_caption(surface, state.caption, width, height)
        self._draw_fps(surface, state.fps, width - padding, height - padding)

    def _draw_active(self, surface: pygame.Surface, state: HUDState, x: int, max_width: int) -> None:
        y = 20
        title = "Drawing: "
        if state.active_task:
            event = state.active_task.event
            donor = event.donor or "anonymous"
            title += f"{donor} — {event.amount} {event.currency}"
        else:
            title += "waiting for request"
        title_surf = self._title_font.render(title, True, self._fg)
        surface.blit(title_surf, (x, y))
        y += title_surf.get_height() + 10

        if state.active_task:
            message_lines = wrap(state.active_task.event.message or "", width=50)
            for line in message_lines[:5]:
                message_surf = self._body_font.render(line, True, self._fg)
                surface.blit(message_surf, (x, y))
                y += message_surf.get_height() + 4

        y += 10
        self._draw_progress(surface, x, y, max_width - x, state.progress, state.hold_remaining, state.hold_total)

    def _draw_progress(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        progress: float,
        hold_remaining: float,
        hold_total: float,
    ) -> None:
        height = 20
        pygame.draw.rect(surface, self._fg, pygame.Rect(x, y, width, height), width=2)
        inner_width = int(width * max(0.0, min(1.0, progress)))
        pygame.draw.rect(surface, self._accent, pygame.Rect(x + 2, y + 2, inner_width - 4 if inner_width > 4 else 0, height - 4))

        if hold_remaining > 0 and hold_total > 0:
            text = f"Showing result: {hold_remaining:0.0f}s remaining"
            label = self._small_font.render(text, True, self._warning)
            surface.blit(label, (x, y + height + 6))

    def _draw_queue(
        self,
        surface: pygame.Surface,
        queue_preview: Sequence[RenderTask],
        x: int,
        y: int,
        max_width: int,
    ) -> None:
        header = self._title_font.render("Next up", True, self._fg)
        surface.blit(header, (x, y))
        y += header.get_height() + 10

        for idx, task in enumerate(queue_preview[:5], start=1):
            donor = task.event.donor or "anonymous"
            label = f"{idx}. {donor} — {task.event.amount} {task.event.currency}"
            label_surf = self._body_font.render(label, True, self._fg)
            surface.blit(label_surf, (x, y))
            y += label_surf.get_height() + 4

            if task.event.message:
                for line in wrap(task.event.message, width=40):
                    line_surf = self._small_font.render(line, True, self._fg)
                    surface.blit(line_surf, (x + 20, y))
                    y += line_surf.get_height() + 2
            y += 6

    def _draw_caption(self, surface: pygame.Surface, caption: str, width: int, height: int) -> None:
        caption_surf = self._title_font.render(caption, True, self._fg)
        rect = caption_surf.get_rect(center=(width // 2, height - 40))
        surface.blit(caption_surf, rect)

    def _draw_fps(self, surface: pygame.Surface, fps: float, x: int, y: int) -> None:
        label = self._small_font.render(f"FPS: {fps:0.1f}", True, self._fg)
        rect = label.get_rect(bottomright=(x, y))
        surface.blit(label, rect)

