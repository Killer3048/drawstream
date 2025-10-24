"""Helper utilities for pygame surfaces."""

from __future__ import annotations

import pygame


def init_pygame(window_title: str, width: int, height: int) -> None:
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption(window_title)
    pygame.display.set_mode((width, height))


def create_canvas(width: int, height: int, color: tuple[int, int, int] | None = None) -> pygame.Surface:
    surface = pygame.Surface((width, height), flags=pygame.SRCALPHA)
    if color is not None:
        surface.fill(color)
    return surface


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def upscale(surface: pygame.Surface, scale: int) -> pygame.Surface:
    width, height = surface.get_size()
    return pygame.transform.scale(surface, (width * scale, height * scale))

