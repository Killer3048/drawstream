"""Convert generated pixel art into Canvas-DSL steps."""

from __future__ import annotations

import itertools
from collections import Counter
from typing import List

from PIL import Image

from ..canvas_dsl import CanvasDocument, ensure_canvas_document
from ..config import Settings, get_settings


class ImageToCanvas:
    """Quantize an image and produce Canvas-DSL instructions."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._size = self._settings.pixel_output_size
        self._palette_colors = self._settings.pixel_palette_colors
        self._chunk_size = self._settings.pixel_stroke_chunk_size
        self._base_duration = self._settings.pixel_animation_base_duration_ms
        self._per_pixel = self._settings.pixel_animation_per_pixel_ms
        self._delay_step = self._settings.pixel_animation_delay_ms

    def build(self, image: Image.Image, caption: str = "All for you") -> CanvasDocument:
        document, _ = self._build(image, caption, return_debug=False)
        return document

    def build_with_debug(self, image: Image.Image, caption: str = "All for you"):
        return self._build(image, caption, return_debug=True)

    def _build(self, image: Image.Image, caption: str, return_debug: bool):
        resized = image.resize((self._size, self._size), Image.NEAREST)
        quantized = resized.quantize(colors=self._palette_colors, method=Image.MEDIANCUT)
        palette = self._extract_palette(quantized)
        data = list(quantized.getdata())
        width, height = quantized.size

        counts = Counter(data)
        if not counts:
            raise ValueError("Quantized image contains no data")
        bg_index = counts.most_common(1)[0][0]

        steps = []
        debug_layers = []
        ordered_indices = [idx for idx, _ in counts.most_common()]
        delay = 0
        order_counter = 0
        for idx in ordered_indices:
            if idx == bg_index:
                continue
            color_hex = palette.get(idx)
            if not color_hex:
                continue
            points = self._collect_points(data, width, height, idx)
            if not points:
                continue
            for stroke in self._chunk_points(points):
                duration = self._stroke_duration(len(stroke))
                step = {
                    "op": "pixels",
                    "color": color_hex,
                    "points": stroke,
                    "animate": {
                        "mode": "pixel_reveal",
                        "duration_ms": duration,
                        "delay_ms": delay,
                        "ease": "ease_in_out",
                    },
                }
                steps.append(step)
                if return_debug:
                    debug_layers.append(
                        {
                            "color": color_hex,
                            "points": stroke,
                            "order": order_counter,
                        }
                    )
                order_counter += 1
                delay += self._delay_step

        document = {
            "version": "1.0",
            "caption": caption,
            "canvas": {
                "w": self._size,
                "h": self._size,
                "bg": palette.get(bg_index, "#000000"),
            },
            "palette": self._ordered_palette(palette, counts),
            "steps": steps,
        }
        return ensure_canvas_document(document), debug_layers if return_debug else None

    def _collect_points(self, data: List[int], width: int, height: int, target_idx: int) -> list[list[int]]:
        points: list[list[int]] = []
        for y in range(height):
            row_offset = y * width
            for x in range(width):
                if data[row_offset + x] == target_idx:
                    points.append([x, y])
        return points

    def _chunk_points(self, points: list[list[int]]) -> list[list[list[int]]]:
        if not points:
            return []
        ordered = sorted(points, key=lambda pt: (pt[1], pt[0]))
        strokes: list[list[list[int]]] = []
        for i in range(0, len(ordered), self._chunk_size):
            strokes.append(ordered[i : i + self._chunk_size])
        return strokes

    def _stroke_duration(self, pixels: int) -> int:
        return int(self._base_duration + pixels * self._per_pixel)

    def _ordered_palette(self, palette_map: dict[int, str], counts: Counter) -> list[str]:
        ordered: list[str] = []
        for idx, _ in counts.most_common():
            color = palette_map.get(idx)
            if color and color not in ordered:
                ordered.append(color)
        return ordered

    def _extract_palette(self, image: Image.Image) -> dict[int, str]:
        raw = image.getpalette()
        palette: dict[int, str] = {}
        if not raw:
            return palette
        chunks = [raw[i : i + 3] for i in range(0, len(raw), 3)]
        for idx, (r, g, b) in enumerate(chunks):
            palette[idx] = f"#{r:02X}{g:02X}{b:02X}"
        return palette
