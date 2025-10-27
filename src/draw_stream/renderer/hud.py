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
    queue_length: int
    caption: str
    fps: float


class HudRenderer:
    def __init__(self, window_size: tuple[int, int]) -> None:
        width, _ = window_size
        base_size = max(20, width // 60)
        self._title_font = pygame.font.SysFont("arial", base_size + 6, bold=True)
        self._body_font = pygame.font.SysFont("arial", base_size)
        self._small_font = pygame.font.SysFont("arial", base_size - 6)
        self._badge_font = pygame.font.SysFont("arial", base_size - 8, bold=True)
        self._fg = hex_to_rgb("#FFFFFF")
        self._accent = hex_to_rgb("#66CCFF")
        self._warning = hex_to_rgb("#FF6666")
        self._panel_bg = (*hex_to_rgb("#141A28"), 220)
        self._panel_outline = (*hex_to_rgb("#4B73FF"), 100)
        self._padding = 32

    def draw(self, surface: pygame.Surface, state: HUDState, canvas_rect: pygame.Rect) -> None:
        width, height = surface.get_size()
        panel_x = canvas_rect.right + self._padding
        panel_width = max(320, width - panel_x - self._padding)
        if panel_x + panel_width + self._padding > width:
            panel_x = max(self._padding, width - panel_width - self._padding)

        info_rect = pygame.Rect(panel_x, self._padding, panel_width, (height - 3 * self._padding) // 2)
        queue_rect = pygame.Rect(panel_x, info_rect.bottom + 24, panel_width, height - info_rect.bottom - (self._padding // 2))

        self._draw_card(surface, info_rect)
        self._draw_card(surface, queue_rect)
        self._draw_active(surface, state, info_rect.inflate(-32, -32))
        self._draw_queue(surface, state.queue_preview, state.queue_length, queue_rect.inflate(-32, -32))
        self._draw_caption(surface, state.caption, width, height)
        self._draw_fps(surface, state.fps, width - self._padding, height - self._padding)
        self._draw_canvas_badge(surface, state, canvas_rect)

    def _draw_card(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        card = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(card, self._panel_bg, card.get_rect(), border_radius=28)
        pygame.draw.rect(card, self._panel_outline, card.get_rect(), width=2, border_radius=28)
        surface.blit(card, rect.topleft)

    def _draw_active(self, surface: pygame.Surface, state: HUDState, rect: pygame.Rect) -> None:
        x = rect.x
        y = rect.y
        title = "What we're drawing"
        if state.active_task:
            event = state.active_task.event
            donor = event.donor or "anonymous"
            subtitle = f"{donor} — {event.amount} {event.currency}"
        else:
            subtitle = "Awaiting next supporter"
        title_surf = self._title_font.render(title, True, self._fg)
        surface.blit(title_surf, (x, y))
        y += title_surf.get_height() + 10

        subtitle_surf = self._small_font.render(subtitle, True, self._accent)
        surface.blit(subtitle_surf, (x, y))
        y += subtitle_surf.get_height() + 8

        if state.active_task:
            message_lines = wrap(state.active_task.event.message or "", width=38)
            for line in message_lines[:6]:
                message_surf = self._body_font.render(line, True, self._fg)
                surface.blit(message_surf, (x, y))
                y += message_surf.get_height() + 4

        y += 10
        self._draw_progress(surface, x, y, rect.width - 20, state.progress, state.hold_remaining, state.hold_total)

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
        queue_length: int,
        rect: pygame.Rect,
    ) -> None:
        x = rect.x
        y = rect.y + rect.height // 2
        header = self._title_font.render(f"Queue · {queue_length}", True, self._fg)
        surface.blit(header, (x, y))
        y += header.get_height() + 8

        for idx, task in enumerate(queue_preview[:5], start=1):
            donor = task.event.donor or "anonymous"
            label = f"{idx}. {donor} — {task.event.amount} {task.event.currency}"
            label_surf = self._body_font.render(label, True, self._fg)
            surface.blit(label_surf, (x, y))
            y += label_surf.get_height() + 4

            if task.event.message:
                for line in wrap(task.event.message, width=36):
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

    def _draw_canvas_badge(self, surface: pygame.Surface, state: HUDState, canvas_rect: pygame.Rect) -> None:
        badge_rect = pygame.Rect(canvas_rect.x, canvas_rect.top - 48, 200, 36)
        badge = pygame.Surface(badge_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(badge, (20, 24, 36, 200), badge.get_rect(), border_radius=18)
        pygame.draw.rect(badge, (102, 204, 255, 160), badge.get_rect(), width=1, border_radius=18)
        surface.blit(badge, badge_rect.topleft)
        text = "LIVE PAINTING"
        if state.active_task and state.active_task.event.donor:
            text = f"LIVE · {state.active_task.event.donor}"
        label = self._badge_font.render(text.upper(), True, self._fg)
        label_rect = label.get_rect(center=badge_rect.center)
        surface.blit(label, label_rect)
