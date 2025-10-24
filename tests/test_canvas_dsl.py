import pytest
from pydantic import ValidationError

from draw_stream.canvas_dsl import CanvasDocument


def test_canvas_document_with_steps() -> None:
    data = {
        "version": "1.0",
        "canvas": {"w": 96, "h": 96, "bg": "#202020"},
        "caption": "All for you",
        "steps": [
            {
                "op": "rect",
                "x": 10,
                "y": 10,
                "w": 20,
                "h": 20,
                "fill": "#FF0000",
                "animate": {"mode": "fill", "duration_ms": 500},
            }
        ],
    }

    document = CanvasDocument.model_validate(data)
    assert document.canvas.w == 96
    assert document.steps is not None
    assert document.caption == "All for you"


def test_canvas_document_render_text() -> None:
    data = {
        "version": "1.0",
        "canvas": {"w": 96, "h": 96, "bg": "#202020"},
        "caption": "All for you",
        "render_text": "You are too small",
        "duration_sec": 45,
    }

    document = CanvasDocument.model_validate(data)
    assert document.render_text == "You are too small"
    assert document.steps is None
    assert document.duration_sec == 45


def test_canvas_document_requires_steps_or_text() -> None:
    data = {
        "version": "1.0",
        "canvas": {"w": 96, "h": 96, "bg": "#202020"},
        "caption": "All for you",
    }

    with pytest.raises(ValidationError):
        CanvasDocument.model_validate(data)
