"""Craft a hand-authored Canvas-DSL plan and export JSON + PNG for reference."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src"))

from draw_stream.canvas_dsl import ensure_canvas_document
from draw_stream.config import get_settings
from draw_stream.renderer.animations import StepPreparer
from draw_stream.renderer.surface import create_canvas, hex_to_rgb, upscale


REFERENCE_PLAN = {
    "version": "1.0",
    "caption": "All for you",
    "canvas": {"w": 96, "h": 96, "bg": "#0B0D26"},
    "palette": [
        "#0B0D26",
        "#141C3C",
        "#1F2C4F",
        "#27386B",
        "#32457A",
        "#F8F3C3",
        "#F2C35B",
        "#A86D3F",
        "#603F2B",
        "#3D252A",
        "#6AF2F0",
        "#A5F5F4",
    ],
    "steps": [
        {"op": "rect", "x": 0, "y": 0, "w": 96, "h": 96, "fill": "#141C3C"},
        {"op": "rect", "x": 0, "y": 0, "w": 96, "h": 28, "fill": "#1F2C4F"},
        {"op": "rect", "x": 0, "y": 28, "w": 96, "h": 12, "fill": "#27386B"},
        {"op": "rect", "x": 0, "y": 40, "w": 96, "h": 12, "fill": "#32457A"},
        {"op": "polygon", "points": [[6, 62], [28, 34], [52, 62]], "fill": "#27386B"},
        {"op": "polygon", "points": [[40, 62], [70, 30], [90, 62]], "fill": "#1F2C4F"},
        {"op": "rect", "x": 0, "y": 62, "w": 96, "h": 6, "fill": "#1B2337"},
        {"op": "rect", "x": 0, "y": 68, "w": 96, "h": 8, "fill": "#222C44"},
        {
            "op": "group",
            "animate": {"mode": "fill", "duration_ms": 900},
            "steps": [
                {"op": "rect", "x": 34, "y": 56, "w": 28, "h": 20, "fill": "#603F2B"},
                {"op": "polygon", "points": [[30, 56], [48, 44], [66, 56]], "fill": "#3D252A"},
                {"op": "rect", "x": 54, "y": 62, "w": 6, "h": 6, "fill": "#F2C35B"},
                {"op": "rect", "x": 42, "y": 66, "w": 8, "h": 10, "fill": "#2A1A1E"},
                {"op": "rect", "x": 44, "y": 68, "w": 4, "h": 6, "fill": "#151013"},
            ],
        },
        {"op": "polygon", "points": [[48, 44], [52, 40], [56, 44], [52, 50]], "fill": "#6AF2F0"},
        {"op": "circle", "cx": 16, "cy": 16, "r": 6, "fill": "#F8F3C3"},
        {
            "op": "pixels",
            "color": "#A5F5F4",
            "points": [
                [12, 8],
                [26, 12],
                [40, 10],
                [54, 6],
                [70, 12],
                [84, 18],
                [18, 22],
                [32, 18],
                [46, 22],
                [60, 18],
                [74, 22],
            ],
        },
        {
            "op": "pixels",
            "color": "#F2C35B",
            "points": [
                [24, 70],
                [28, 72],
                [32, 74],
                [36, 76],
                [40, 78],
                [44, 80],
                [48, 82],
                [52, 84],
                [56, 82],
                [60, 80],
                [64, 78],
                [68, 76],
                [72, 74],
            ],
        },
        {
            "op": "line",
            "x1": 10,
            "y1": 84,
            "x2": 86,
            "y2": 84,
            "width": 1,
            "color": "#2F3A56",
        },
        {
            "op": "pixels",
            "color": "#A5F5F4",
            "points": [[14, 26], [18, 28], [22, 30], [26, 32], [30, 34], [34, 32], [38, 30]],
        },
    ],
}


def main() -> None:
    settings = get_settings()
    document = ensure_canvas_document(REFERENCE_PLAN)

    output_json = Path("assets/examples")
    output_png = Path("out/reference")
    output_json.mkdir(parents=True, exist_ok=True)
    output_png.mkdir(parents=True, exist_ok=True)

    json_path = output_json / "aurora_cabin_plan.json"
    json_path.write_text(json.dumps(REFERENCE_PLAN, indent=2))

    base_surface = create_canvas(document.canvas.w, document.canvas.h, hex_to_rgb(document.canvas.bg))
    preparer = StepPreparer(document.canvas, settings.default_step_duration_ms)
    for step in document.steps or []:
        for prepared in preparer.prepare(step):
            prepared.apply_final(base_surface)

    scaled = upscale(base_surface, settings.window_scale)
    pygame_path = output_png / "aurora_cabin_reference.png"
    from pygame import image

    image.save(scaled, pygame_path.as_posix())
    print(f"Saved {pygame_path}")
    print(f"Saved {json_path}")


if __name__ == "__main__":
    import pygame

    pygame.init()
    pygame.font.init()
    main()
    pygame.quit()
