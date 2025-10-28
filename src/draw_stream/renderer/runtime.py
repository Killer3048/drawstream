"""Renderer runtime orchestrating pygame loop and animations."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

import pygame

from ..canvas_dsl import CanvasDocument
from ..config import Settings, get_settings
from ..models import RenderTask, RenderTaskType
from ..queue import QueueManager
from ..logging import configure_logging
from .animations import PreparedStep, StepPreparer
from .hud import HUDState, HudRenderer
from .surface import create_canvas, hex_to_rgb, init_pygame, upscale


@dataclass(slots=True)
class RendererState:
    active_task: Optional[RenderTask]
    progress: float
    hold_remaining: float
    queue_preview: list[RenderTask]
    fps: float


class RendererRuntime:
    """Main pygame loop managing drawing and HUD rendering."""

    def __init__(self, queue: QueueManager, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._queue = queue
        self._running = False
        self._loop_task: Optional[asyncio.Task[None]] = None
        self._pending_task: Optional[asyncio.Task[RenderTask]] = None

        # drawing state
        self._active_task: Optional[RenderTask] = None
        self._prepared_steps: list[PreparedStep] = []
        self._step_index = 0
        self._step_elapsed = 0.0
        self._step_delay = 0.0
        self._drawing_complete = False
        self._caption = "All for you"
        self._holding_until: Optional[float] = None
        self._task_done_pending = False

        self._base_surface = create_canvas(self._settings.canvas_w, self._settings.canvas_h)
        self._frame_surface = self._base_surface.copy()
        self._display_surface: Optional[pygame.Surface] = None
        self._backdrop_surface: Optional[pygame.Surface] = None
        self._hud: Optional[HudRenderer] = None
        self._clock = pygame.time.Clock()
        self._step_preparer: Optional[StepPreparer] = None
        self._bg_color = hex_to_rgb("#202020")
        self._accent_color = hex_to_rgb("#6C63FF")
        self._shadow_color = hex_to_rgb("#090C12")
        self._skip_requested = False
        self._queue_preview: list[RenderTask] = []
        self._queue_length = 0
        self._canvas_scale = max(1, self._settings.window_scale)
        self._canvas_rect = pygame.Rect(0, 0, self._settings.canvas_w * self._canvas_scale, self._settings.canvas_h * self._canvas_scale)
        self._side_padding = 96
        self._content_gap = 120
        self._canvas_frame_rect = self._canvas_rect.inflate(40, 40)
        self._fallback_overlay: Optional[pygame.Surface] = None
        self._info_panel_width = 0

    async def start(self) -> None:
        if self._running:
            return
        configure_logging()
        window_width = self._settings.display_width
        window_height = self._settings.display_height
        self._compute_canvas_layout(window_width, window_height)
        init_pygame("Draw Stream", window_width, window_height)
        self._display_surface = pygame.display.get_surface()
        self._backdrop_surface = self._build_backdrop_surface(window_width, window_height)
        self._hud = HudRenderer((window_width, window_height), content_gap=self._content_gap)
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop(), name="renderer-loop")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
        pygame.quit()

    def request_skip(self) -> None:
        self._skip_requested = True

    def snapshot(self) -> "RendererState":
        hold_remaining = max(0.0, (self._holding_until or 0) - time.monotonic()) if self._holding_until else 0.0
        return RendererState(
            active_task=self._active_task,
            progress=self._compute_progress(),
            hold_remaining=hold_remaining,
            queue_preview=list(self._queue_preview),
            fps=self._clock.get_fps(),
        )

    async def _run_loop(self) -> None:
        while self._running:
            self._process_events()
            dt_ms = self._clock.tick(self._settings.frame_rate)
            await self._assign_tasks()
            self._advance_animation(dt_ms)
            await self._refresh_preview()
            self._render_frame()
            await asyncio.sleep(0)

    def _process_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False

    async def _assign_tasks(self) -> None:
        if self._active_task is None:
            if self._pending_task is None:
                self._pending_task = asyncio.create_task(self._queue.dequeue())

            if self._pending_task.done():
                try:
                    task = self._pending_task.result()
                except asyncio.CancelledError:  # pragma: no cover
                    self._pending_task = None
                    return
                self._pending_task = None
                self._apply_new_task(task)

    def _apply_new_task(self, task: RenderTask) -> None:
        self._active_task = task
        self._task_done_pending = True
        self._step_index = 0
        self._step_elapsed = 0.0
        self._step_delay = 0.0
        self._holding_until = None
        self._drawing_complete = False
        self._skip_requested = False
        self._fallback_overlay = None

        if task.content_type == RenderTaskType.TEXT:
            self._caption = "All for you"
            self._bg_color = hex_to_rgb("#202020")
            self._base_surface.fill(self._bg_color)
            self._render_text_card(task.fallback_text or "You are too small")
            self._start_hold_timer(task.hold_duration_sec)
            self._drawing_complete = True
            return

        plan = task.require_plan()
        self._caption = plan.caption
        self._bg_color = hex_to_rgb(plan.canvas.bg)
        self._base_surface.fill(self._bg_color)
        self._frame_surface = self._base_surface.copy()

        self._step_preparer = StepPreparer(plan.canvas, self._settings.default_step_duration_ms)
        self._prepared_steps = []
        if plan.steps:
            for step in plan.steps:
                self._prepared_steps.extend(self._step_preparer.prepare(step))

        if self._prepared_steps:
            self._step_delay = self._prepared_steps[0].timeline.delay_ms
        else:
            self._drawing_complete = True
            self._start_hold_timer(self._active_task.hold_duration_sec if self._active_task else None)

    def _render_text_card(self, text: str) -> None:
        display_width = self._canvas_rect.width or (self._settings.canvas_w * self._canvas_scale)
        display_height = self._canvas_rect.height or (self._settings.canvas_h * self._canvas_scale)
        overlay = pygame.Surface((display_width, display_height), pygame.SRCALPHA)
        overlay.fill(self._bg_color)

        max_width = display_width - 96
        font_size = max(28, display_width // 18)
        min_size = 16
        line_spacing = max(12, display_height // 30)

        def layout(size: int) -> tuple[pygame.font.Font, list[str], int]:
            local_font = pygame.font.SysFont("arial", size, bold=True)
            candidate_lines = self._wrap_text(local_font, text, max_width)
            line_height = local_font.size("Ag")[1]
            total = len(candidate_lines) * line_height + max(0, len(candidate_lines) - 1) * line_spacing
            return local_font, candidate_lines, total

        font, lines, total_height = layout(font_size)
        while total_height > display_height - 96 and font_size > min_size:
            font_size -= 2
            font, lines, total_height = layout(font_size)

        start_y = max(48, (display_height - total_height) // 2)
        y = start_y
        for line in lines:
            rendered = font.render(line, True, hex_to_rgb("#FFFFFF"))
            rect = rendered.get_rect(center=(display_width // 2, y + rendered.get_height() // 2))
            overlay.blit(rendered, rect)
            y += rendered.get_height() + line_spacing

        self._fallback_overlay = overlay.convert() if self._display_surface else overlay
        reduced = pygame.transform.smoothscale(overlay, (self._settings.canvas_w, self._settings.canvas_h)).convert()
        self._base_surface = reduced
        self._frame_surface = reduced.copy()

    def _wrap_text(self, font: pygame.font.Font, text: str, max_width: int) -> list[str]:
        if not text:
            return [""]

        words = text.split()
        lines: list[str] = []
        current = ""

        for word in words:
            tentative = f"{current} {word}".strip()
            if tentative and font.size(tentative)[0] <= max_width:
                current = tentative
                continue

            if current:
                lines.append(current)
                current = ""

            if font.size(word)[0] <= max_width:
                current = word
                continue

            for segment in self._break_long_word(font, word, max_width):
                if font.size(segment)[0] <= max_width:
                    lines.append(segment)
                else:  # pragma: no cover - ultra narrow fonts
                    lines.extend(list(segment))

        if current:
            lines.append(current)

        return lines or [""]

    def _break_long_word(self, font: pygame.font.Font, word: str, max_width: int) -> list[str]:
        """Split a single word into multiple segments that fit within ``max_width``."""

        segments: list[str] = []
        buffer = ""
        for char in word:
            candidate = buffer + char
            if font.size(candidate)[0] <= max_width or not buffer:
                buffer = candidate
            else:
                segments.append(buffer)
                buffer = char
        if buffer:
            segments.append(buffer)
        return segments

    def _advance_animation(self, dt_ms: float) -> None:
        if not self._active_task:
            self._base_surface.fill(self._bg_color)
            self._frame_surface = self._base_surface.copy()
            return

        if self._skip_requested:
            self._complete_task(skipped=True)
            return

        now = time.monotonic()
        if self._holding_until is not None:
            if now >= self._holding_until:
                self._complete_task()
            return

        if self._active_task.content_type == RenderTaskType.TEXT:
            # text tasks immediately go to hold
            return

        if self._step_index >= len(self._prepared_steps):
            if not self._drawing_complete:
                self._drawing_complete = True
                self._start_hold_timer(self._active_task.hold_duration_sec if self._active_task else None)
            return

        current = self._prepared_steps[self._step_index]

        if self._step_delay > 0:
            self._step_delay = max(0.0, self._step_delay - dt_ms)
            self._frame_surface = self._base_surface.copy()
            if self._step_delay == 0:
                self._step_elapsed = 0.0
            return

        self._step_elapsed += dt_ms
        duration = current.timeline.duration_ms or self._settings.default_step_duration_ms
        progress = min(1.0, self._step_elapsed / duration)

        self._frame_surface = self._base_surface.copy()
        current.render(self._frame_surface, progress)

        if progress >= 1.0:
            current.apply_final(self._base_surface)
            self._step_index += 1
            self._step_elapsed = 0.0
            if self._step_index < len(self._prepared_steps):
                self._step_delay = self._prepared_steps[self._step_index].timeline.delay_ms
            else:
                self._frame_surface = self._base_surface.copy()

    def _start_hold_timer(self, override: Optional[int] = None) -> None:
        duration = float(override) if override else float(self._settings.show_duration_sec)
        self._holding_until = time.monotonic() + duration

    async def _refresh_preview(self) -> None:
        self._queue_preview = await self._queue.preview(limit=5)
        self._queue_length = await self._queue.size()

    def _render_frame(self) -> None:
        if not self._display_surface or not self._hud:
            return

        active_surface = self._frame_surface if not self._drawing_complete else self._base_surface
        if self._fallback_overlay is not None:
            scaled = self._fallback_overlay
        else:
            scaled = upscale(active_surface, self._canvas_scale)

        progress = self._compute_progress()
        hold_remaining = max(0.0, (self._holding_until or 0) - time.monotonic()) if self._holding_until else 0.0
        hold_total = float(
            (self._active_task.hold_duration_sec if self._active_task else None)
            or self._settings.show_duration_sec
        )
        total_queue = self._queue_length + (1 if self._active_task else 0)
        hud_state = HUDState(
            active_task=self._active_task,
            progress=progress,
            hold_remaining=hold_remaining,
            hold_total=hold_total,
            queue_preview=self._queue_preview,
            queue_length=total_queue,
            caption=self._caption,
            fps=self._clock.get_fps(),
        )

        if self._backdrop_surface:
            self._display_surface.blit(self._backdrop_surface, (0, 0))
        else:
            self._display_surface.fill(self._shadow_color)
        self._draw_canvas_frame()
        self._display_surface.blit(scaled, self._canvas_rect)
        self._hud.draw(self._display_surface, hud_state, self._canvas_rect)
        pygame.display.flip()

    def _compute_progress(self) -> float:
        if not self._active_task:
            return 0.0
        if self._active_task.content_type == RenderTaskType.TEXT:
            return 1.0
        total = len(self._prepared_steps)
        if total == 0:
            return 1.0
        completed = min(self._step_index, total)
        fraction = completed / total
        if self._step_index < total:
            current = self._prepared_steps[self._step_index]
            if current.timeline.duration_ms:
                fraction += min(1.0, self._step_elapsed / current.timeline.duration_ms) / total
        return min(1.0, fraction)

    def _complete_task(self, skipped: bool = False) -> None:
        if self._task_done_pending:
            self._queue.task_done()
            self._task_done_pending = False

        self._active_task = None
        self._prepared_steps = []
        self._step_index = 0
        self._step_elapsed = 0.0
        self._step_delay = 0.0
        self._holding_until = None
        self._drawing_complete = False
        self._caption = "All for you"
        self._base_surface.fill(self._bg_color)
        self._frame_surface = self._base_surface.copy()
        self._skip_requested = False
        self._fallback_overlay = None

    def _compute_canvas_layout(self, window_width: int, window_height: int) -> None:
        info_width = max(int(window_width * 0.34), 520)
        self._info_panel_width = info_width
        available_width = window_width - info_width - self._content_gap - self._side_padding * 2
        max_scale_width = max(1, available_width // self._settings.canvas_w)
        max_scale_height = max(1, (window_height - self._side_padding * 2) // self._settings.canvas_h)
        resolved_scale = min(max_scale_width, max_scale_height, self._settings.window_scale)
        self._canvas_scale = max(1, resolved_scale)
        canvas_px_w = self._settings.canvas_w * self._canvas_scale
        canvas_px_h = self._settings.canvas_h * self._canvas_scale
        left = self._side_padding
        header_offset = self._side_padding
        top = max(header_offset, (window_height - canvas_px_h) // 2)
        self._canvas_rect = pygame.Rect(left, top, canvas_px_w, canvas_px_h)
        self._canvas_frame_rect = self._canvas_rect.inflate(48, 48)

    def _build_backdrop_surface(self, width: int, height: int) -> pygame.Surface:
        surface = pygame.Surface((width, height))
        top = hex_to_rgb("#070A1E")
        mid = hex_to_rgb("#101A3F")
        bottom = hex_to_rgb("#061022")
        for y in range(height):
            t = y / max(1, height - 1)
            if t < 0.55:
                blend = t / 0.55
                base = tuple(int(top[i] * (1 - blend) + mid[i] * blend) for i in range(3))
            else:
                blend = (t - 0.55) / 0.45
                base = tuple(int(mid[i] * (1 - blend) + bottom[i] * blend) for i in range(3))
            pygame.draw.line(surface, base, (0, y), (width, y))

        stripes = pygame.Surface((width, height), pygame.SRCALPHA)
        stripe_color = (*hex_to_rgb("#3C4FEE"), 26)
        step = 140
        for offset in range(-height, width, step):
            pygame.draw.line(
                stripes,
                stripe_color,
                (offset, 0),
                (offset + height, height),
                width=5,
            )
        surface.blit(stripes, (0, 0))

        aura = pygame.Surface((width, height), pygame.SRCALPHA)
        center = (int(width * 0.22), int(height * 0.28))
        max_radius = int(max(width, height) * 0.8)
        for radius in range(max_radius, 0, -20):
            alpha = max(0, 140 - int(radius * 0.08))
            if alpha <= 0:
                continue
            color = (*hex_to_rgb("#2334A3"), alpha)
            pygame.draw.circle(aura, color, center, radius)
        surface.blit(aura, (0, 0))

        vignette = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(vignette, (0, 0, 0, 160), vignette.get_rect(), border_radius=28)
        vignette = pygame.transform.gaussian_blur(vignette, 18) if hasattr(pygame.transform, "gaussian_blur") else pygame.transform.smoothscale(vignette, (width, height))
        surface.blit(vignette, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        return surface

    def _draw_canvas_frame(self) -> None:
        frame_rect = self._canvas_frame_rect
        glow_rect = frame_rect.inflate(40, 40)
        glow_surface = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow_surface, (*self._accent_color, 18), glow_surface.get_rect(), border_radius=90)
        self._display_surface.blit(glow_surface, glow_rect.topleft, special_flags=pygame.BLEND_RGBA_ADD)

        shadow_rect = frame_rect.inflate(28, 28)
        shadow_surface = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow_surface, (5, 6, 12, 160), shadow_surface.get_rect(), border_radius=72)
        self._display_surface.blit(shadow_surface, shadow_rect.topleft)

        frame_surface = pygame.Surface(frame_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(frame_surface, (14, 18, 32, 220), frame_surface.get_rect(), border_radius=50)
        pygame.draw.rect(frame_surface, (*self._accent_color, 200), frame_surface.get_rect(), width=3, border_radius=50)
        inner = frame_surface.get_rect().inflate(-20, -20)
        pygame.draw.rect(frame_surface, (9, 11, 20, 240), inner, border_radius=40)
        self._display_surface.blit(frame_surface, frame_rect.topleft)
