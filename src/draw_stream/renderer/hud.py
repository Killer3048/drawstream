"""Heads-up display rendering for the stream window.

Now includes Twitch-style safety filtering:
we mask hateful / harassing slurs and self-harm bait phrases that are
disallowed under Twitch's hateful conduct / harassment rules (race, religion,
sexual orientation, gender identity, disability, etc.) as well as phrases
Twitch itself has called out like "simp", "incel", "virgin", and self-harm
incitement ("kys", "kill yourself"). The goal is to keep them from appearing
on-stream in donor names / messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pygame
import re

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
    def __init__(self, window_size: tuple[int, int], *, content_gap: int = 48) -> None:
        width, _ = window_size
        base_size = max(24, width // 64)
        self._hero_font = pygame.font.SysFont("arial", base_size + 24, bold=True)
        self._title_font = pygame.font.SysFont("arial", base_size + 10, bold=True)
        self._body_font = pygame.font.SysFont("arial", base_size)
        self._small_font = pygame.font.SysFont("arial", base_size - 6)
        self._mono_font = pygame.font.SysFont("consolas", base_size - 10)
        self._badge_font = pygame.font.SysFont("arial", base_size - 8, bold=True)
        self._fg = hex_to_rgb("#F1F5FF")
        self._secondary = hex_to_rgb("#92A4FF")
        self._accent = hex_to_rgb("#6D7CFF")
        self._accent_alt = hex_to_rgb("#58E9FF")
        self._warning = hex_to_rgb("#FF6F91")
        self._panel_bg_top = hex_to_rgb("#14192F")
        self._panel_bg_bottom = hex_to_rgb("#0F1325")
        self._padding = 56
        self._content_gap = content_gap
        self._banned_terms = [
            "nigger",
            "nigga",
            "niglet",
            "porchmonkey",
            "porch monkey",
            "coon",
            "kike",
            "spic",
            "wetback",
            "chink",
            "gook",
            "paki",
            "faggot",
            "fag",
            "dyke",
            "tranny",
            "trannie",
            "trannies",
            "retard",
            "retarded",
            "cripple",
            "crippled",
            "simp",
            "incel",
            "virgin",
            "kys",
            "kill yourself",
            "killyourself",
            "kill urself",
            "негр",
            "нигер",
            "ниггер",
            "чурка",
            "чурки",
            "хач",
            "хачи",
            "хача",
            "пидор",
            "пидр",
            "пидорас",
            "пидорасы",
            "пидарас",
            "пидорасина",
            "пидрила",
            "гомик",
            "жид",
            "жиды",
            "жидовка",
            "жидов",
            "жидовина",
            "москаль",
            "москали",
            "даун",
            "калека"
            "pidor",
            "pidaras",
            "pidoras",
            "pidorass",
            "negr",
        ]

        self._banned_patterns = [
            re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            for term in self._banned_terms
        ]

    def _censor_match(self, match: re.Match) -> str:
        word = match.group(0)
        if len(word) <= 2:
            return "*" * len(word)
        return word[0] + "**" + word[-1]

    def _sanitize_text(self, text: str) -> str:
        """Mask any banned terms in the given text."""
        if not text:
            return text
        result = text
        for pattern in self._banned_patterns:
            result = pattern.sub(self._censor_match, result)
        return result

    def draw(self, surface: pygame.Surface, state: HUDState, canvas_rect: pygame.Rect) -> None:
        width, height = surface.get_size()
        header_height = 64
        header_rect = self._draw_header(surface, state, width, header_height)
        self._draw_status_chip(surface, state, canvas_rect, header_rect)

        panel_x = canvas_rect.right + self._content_gap
        panel_width = max(560, width - panel_x - self._padding)
        if panel_x + panel_width + self._padding > width:
            panel_x = max(self._padding, width - panel_width - self._padding)

        info_top = self._padding + header_height + 12
        available_height = height - info_top - 140
        info_rect = pygame.Rect(panel_x, info_top, panel_width, int(available_height * 0.6))
        queue_top = info_rect.bottom + 20
        queue_rect = pygame.Rect(panel_x, queue_top, panel_width, available_height - info_rect.height - 20)
        footer_rect = pygame.Rect(self._padding, height - 84, width - 2 * self._padding, 72)

        self._draw_glass_panel(surface, info_rect)
        self._draw_glass_panel(surface, queue_rect)
        self._draw_active(surface, state, info_rect.inflate(-48, -48))
        self._draw_queue(surface, state.queue_preview, state.queue_length, queue_rect.inflate(-48, -48))
        self._draw_footer(surface, state, footer_rect)
        self._draw_canvas_badge(surface, state, canvas_rect)

    def _draw_glass_panel(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        shadow = pygame.Surface((rect.width + 40, rect.height + 40), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (8, 10, 20, 160), shadow.get_rect(), border_radius=46)
        shadow = pygame.transform.smoothscale(shadow, shadow.get_size())
        surface.blit(shadow, (rect.x - 20, rect.y - 20))

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            panel,
            (self._panel_bg_top[0], self._panel_bg_top[1], self._panel_bg_top[2], 220),
            panel.get_rect(),
            border_radius=36,
        )
        pygame.draw.rect(panel, (*self._accent, 110), panel.get_rect(), width=2, border_radius=36)
        surface.blit(panel, rect.topleft)

    def _draw_header(self, surface: pygame.Surface, state: HUDState, width: int, height: int) -> pygame.Rect:
        rect = pygame.Rect(self._padding, self._padding, width - 2 * self._padding, height)
        banner = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(banner, (18, 24, 42, 210), banner.get_rect(), border_radius=34)
        pygame.draw.rect(banner, (*self._accent, 120), banner.get_rect(), width=2, border_radius=34)
        surface.blit(banner, rect.topleft)

        title = self._hero_font.render("Draw Stream", True, self._fg)
        title_rect = title.get_rect(midleft=(rect.x + 32, rect.centery))
        surface.blit(title, title_rect)
        return rect

    def _draw_status_chip(
        self,
        surface: pygame.Surface,
        state: HUDState,
        canvas_rect: pygame.Rect,
        header_rect: pygame.Rect,
    ) -> None:
        if state.active_task:
            donor = state.active_task.event.donor or "anonymous"
            chip_text = f"Thank you, {donor}!"
        else:
            chip_text = "Waiting for the next hero"

        max_width = header_rect.width - 96
        padding_x, padding_y = 18, 10
        _, label, chip_width, chip_height = self._chip_metrics(chip_text, max_width, padding_x, padding_y)
        chip_x = header_rect.x + (header_rect.width - chip_width) // 2
        chip_y = header_rect.bottom + 20
        chip_rect = pygame.Rect(chip_x, chip_y, chip_width, chip_height)
        self._render_chip(surface, chip_rect, label, padding_x, padding_y)

    def _draw_active(self, surface: pygame.Surface, state: HUDState, rect: pygame.Rect) -> None:
        x = rect.x
        y = rect.y
        title = self._title_font.render("Now Painting", True, self._fg)
        surface.blit(title, (x, y))
        y += title.get_height() + 12

        if state.active_task:
            event = state.active_task.event
            subtitle = f"{event.amount} {event.currency} — {event.donor or 'anonymous'}"
        else:
            subtitle = "Awaiting the next supporter"
        y = self._render_wrapped(
            surface,
            self._small_font,
            subtitle,
            self._secondary,
            x,
            y,
            rect.width,
            max_lines=2,
            line_spacing=4,
        )
        y += 12

        message_box_height = rect.height - (y - rect.y) - 120
        message_rect = pygame.Rect(x, y, rect.width, max(120, message_box_height))
        self._draw_message_panel(surface, state, message_rect)
        y = message_rect.bottom + 24

        bar_rect = pygame.Rect(x, y, rect.width, 30)
        self._draw_progress_bar(surface, bar_rect, state.progress)
        y += bar_rect.height + 10

        if state.hold_remaining > 0:
            hold_text = f"Result on screen for {state.hold_remaining:0.0f}s"
            hold_label = self._small_font.render(self._sanitize_text(hold_text), True, self._warning)
            surface.blit(hold_label, (x, y))

    def _draw_message_panel(self, surface: pygame.Surface, state: HUDState, rect: pygame.Rect) -> None:
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (18, 22, 38, 210), panel.get_rect(), border_radius=32)
        pygame.draw.rect(panel, (*self._accent_alt, 110), panel.get_rect(), width=2, border_radius=32)
        surface.blit(panel, rect.topleft)

        if state.active_task:
            message = state.active_task.event.message or ""
        else:
            message = "Queue is empty — send in your idea!"

        text_x = rect.x + 24
        text_y = rect.y + 20
        self._render_wrapped(
            surface,
            self._body_font,
            message,
            self._fg,
            text_x,
            text_y,
            rect.width - 48,
            max_lines=6,
            line_spacing=6,
        )

    def _draw_progress_bar(self, surface: pygame.Surface, rect: pygame.Rect, progress: float) -> None:
        pygame.draw.rect(surface, (18, 22, 38, 220), rect, border_radius=18)
        pygame.draw.rect(surface, (*self._accent, 200), rect, width=2, border_radius=18)
        inner = rect.inflate(-8, -8)
        fill_width = int(inner.width * max(0.0, min(1.0, progress)))
        if fill_width > 0:
            fill_rect = pygame.Rect(inner.x, inner.y, fill_width, inner.height)
            gradient = pygame.Surface(fill_rect.size, pygame.SRCALPHA)
            for x in range(fill_rect.width):
                t = x / max(1, fill_rect.width - 1)
                color = (
                    int(self._accent[0] * (0.8 + 0.2 * t)),
                    int(self._accent_alt[1] * (0.7 + 0.3 * (1 - t))),
                    int(self._accent_alt[2] * (0.7 + 0.3 * t)),
                    230,
                )
                pygame.draw.line(gradient, color, (x, 0), (x, fill_rect.height))
            surface.blit(gradient, fill_rect.topleft)

        gloss = pygame.Surface(inner.size, pygame.SRCALPHA)
        pygame.draw.rect(
            gloss,
            (255, 255, 255, 40),
            gloss.get_rect().inflate(-inner.width * 0.1, -inner.height * 0.4),
            border_radius=12,
        )
        surface.blit(gloss, inner.topleft, special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_queue(
        self,
        surface: pygame.Surface,
        queue_preview: Sequence[RenderTask],
        queue_length: int,
        rect: pygame.Rect,
    ) -> None:
        title = self._title_font.render("Queue", True, self._fg)
        surface.blit(title, (rect.x, rect.y))
        chip_rect = self._draw_chip(
            surface,
            f"{queue_length} waiting",
            (rect.x + title.get_width() + 24, rect.y + 4),
            max_width=rect.width - title.get_width() - 48,
        )

        y = rect.y + max(title.get_height(), chip_rect.height) + 20
        if not queue_preview:
            placeholder = self._small_font.render("No pending requests", True, self._secondary)
            surface.blit(placeholder, (rect.x, y))
            return

        card_height = 96
        for idx, task in enumerate(queue_preview[:5], start=1):
            entry_rect = pygame.Rect(rect.x, y, rect.width, card_height)
            self._draw_queue_entry(surface, entry_rect, idx, task)
            y += card_height + 14

    def _draw_queue_entry(self, surface: pygame.Surface, rect: pygame.Rect, index: int, task: RenderTask) -> None:
        card = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(card, (18, 22, 38, 210), card.get_rect(), border_radius=30)
        pygame.draw.rect(card, (*self._accent, 120), card.get_rect(), width=2, border_radius=30)
        surface.blit(card, rect.topleft)

        circle_radius = 22
        circle_center = (rect.x + 32 + circle_radius, rect.y + rect.height // 2)
        pygame.draw.circle(surface, (*self._accent_alt, 220), circle_center, circle_radius)
        index_label = self._badge_font.render(str(index), True, self._fg)
        idx_rect = index_label.get_rect(center=circle_center)
        surface.blit(index_label, idx_rect)

        donor = task.event.donor or "anonymous"
        header_text = f"{donor} · {task.event.amount} {task.event.currency}"
        header_y = rect.y + 18
        safe_header = self._sanitize_text(header_text)
        surface.blit(self._body_font.render(safe_header, True, self._fg), (rect.x + 80, header_y))

        if task.event.message:
            message_y = header_y + self._body_font.get_linesize() + 4
            self._render_wrapped(
                surface,
                self._small_font,
                task.event.message,
                self._secondary,
                rect.x + 80,
                message_y,
                rect.width - 100,
                max_lines=3,
                line_spacing=4,
            )

    def _draw_footer(self, surface: pygame.Surface, state: HUDState, rect: pygame.Rect) -> None:
        footer = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(footer, (12, 16, 28, 235), footer.get_rect(), border_radius=28)
        pygame.draw.rect(footer, (*self._accent, 120), footer.get_rect(), width=2, border_radius=28)
        surface.blit(footer, rect.topleft)

        caption = state.caption or "All for you"
        safe_caption = self._sanitize_text(caption)
        caption_label = self._title_font.render(safe_caption, True, self._fg)
        caption_rect = caption_label.get_rect(center=(rect.centerx, rect.centery))
        surface.blit(caption_label, caption_rect)

        # Counters removed per design request.

    def _draw_canvas_badge(self, surface: pygame.Surface, state: HUDState, canvas_rect: pygame.Rect) -> None:
        text = "LIVE PAINTING"
        if state.active_task and state.active_task.event.donor:
            text = f"LIVE · {state.active_task.event.donor}"
        safe_text = self._sanitize_text(text).upper()
        label = self._badge_font.render(safe_text, True, self._fg)
        badge_width = max(260, label.get_width() + 80)
        badge_rect = pygame.Rect(canvas_rect.x + 32, canvas_rect.top - 60, badge_width, 44)
        badge = pygame.Surface(badge_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(badge, (23, 29, 50, 230), badge.get_rect(), border_radius=22)
        pygame.draw.rect(badge, (*self._accent_alt, 140), badge.get_rect(), width=2, border_radius=22)
        surface.blit(badge, badge_rect.topleft)
        label_rect = label.get_rect(center=badge_rect.center)
        surface.blit(label, label_rect)

    def _draw_chip(
        self,
        surface: pygame.Surface,
        text: str,
        origin: tuple[int, int],
        max_width: int | None = None,
    ) -> pygame.Rect:
        padding_x, padding_y = 18, 10
        _, label, width, height = self._chip_metrics(text, max_width, padding_x, padding_y)
        chip_rect = pygame.Rect(origin[0], origin[1], width, height)
        self._render_chip(surface, chip_rect, label, padding_x, padding_y)
        return chip_rect

    def _chip_metrics(
        self,
        text: str,
        max_width: int | None,
        padding_x: int,
        padding_y: int,
    ) -> tuple[str, pygame.Surface, int, int]:
        safe_text = self._sanitize_text(text)
        label_text = self._truncate_text(
            self._small_font,
            safe_text,
            (max_width - padding_x * 2) if max_width else None,
        )
        label = self._small_font.render(label_text, True, self._fg)
        width = label.get_width() + padding_x * 2
        if max_width is not None:
            width = min(width, max_width)
        height = label.get_height() + padding_y * 2
        return label_text, label, width, height

    def _render_chip(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: pygame.Surface,
        padding_x: int,
        padding_y: int,
    ) -> None:
        chip = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(chip, (18, 22, 38, 220), chip.get_rect(), border_radius=20)
        pygame.draw.rect(chip, (*self._accent_alt, 140), chip.get_rect(), width=2, border_radius=20)
        surface.blit(chip, rect.topleft)
        surface.blit(label, (rect.x + padding_x, rect.y + padding_y))

    def _truncate_text(self, font: pygame.font.Font, text: str, max_width: int | None) -> str:
        if max_width is None or font.size(text)[0] <= max_width:
            return text
        ellipsis = "…"
        max_width = max(max_width, font.size(ellipsis)[0])
        trimmed = text
        while trimmed and font.size(trimmed + ellipsis)[0] > max_width:
            trimmed = trimmed[:-1]
        return (trimmed + ellipsis) if trimmed else ellipsis

    def _render_wrapped(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        color: tuple[int, int, int],
        x: int,
        y: int,
        max_width: int,
        max_lines: int | None = None,
        line_spacing: int = 4,
    ) -> int:
        if not text:
            return y

        safe_text = self._sanitize_text(text)

        lines = self._wrap_text(font, safe_text, max_width)
        if max_lines is not None:
            lines = lines[:max_lines]

        for line in lines:
            rendered = font.render(line, True, color)
            surface.blit(rendered, (x, y))
            y += rendered.get_height() + line_spacing

        return y

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

            pieces = self._break_long_word(font, word, max_width)
            if pieces:
                lines.extend(pieces[:-1])
                current = pieces[-1]

        if current:
            lines.append(current)

        return lines or [""]

    def _break_long_word(self, font: pygame.font.Font, word: str, max_width: int) -> list[str]:
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
