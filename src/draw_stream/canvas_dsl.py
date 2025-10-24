"""Canvas DSL schema definitions and helpers."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


def _validate_hex_color(hex_color: str) -> str:
    if not isinstance(hex_color, str) or not hex_color.startswith("#") or len(hex_color) not in (4, 7):
        raise ValueError("Color must be a hex string like '#FFF' or '#11AA22'")
    try:
        int(hex_color[1:], 16)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError("Invalid hex color") from exc
    return hex_color


class AnimationConfig(BaseModel):
    """Animation metadata for a drawing step."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["stroke", "fill", "pixel_reveal"] = Field(...)
    speed_px_per_s: Optional[float] = Field(None, ge=0)
    duration_ms: Optional[int] = Field(None, ge=1)
    delay_ms: Optional[int] = Field(None, ge=0)
    ease: Literal["linear", "ease_in_out"] = Field("linear")


class StepBase(BaseModel):
    """Base fields common to all steps."""

    model_config = ConfigDict(extra="forbid")

    animate: Optional[AnimationConfig] = None


class RectStep(StepBase):
    op: Literal["rect"]
    x: int
    y: int
    w: int
    h: int
    fill: Optional[str] = Field(default=None)
    outline: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def _validate_colors(self) -> "RectStep":
        if self.fill is not None:
            self.fill = _validate_hex_color(self.fill)
        if self.outline is not None:
            self.outline = _validate_hex_color(self.outline)
        return self


class CircleStep(StepBase):
    op: Literal["circle"]
    cx: int
    cy: int
    r: int = Field(..., ge=0)
    fill: Optional[str] = Field(default=None)
    outline: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def _validate_colors(self) -> "CircleStep":
        if self.fill is not None:
            self.fill = _validate_hex_color(self.fill)
        if self.outline is not None:
            self.outline = _validate_hex_color(self.outline)
        return self


class LineStep(StepBase):
    op: Literal["line"]
    x1: int
    y1: int
    x2: int
    y2: int
    width: int = Field(1, ge=1)
    color: str = Field(...)

    @model_validator(mode="after")
    def _validate_color(self) -> "LineStep":
        self.color = _validate_hex_color(self.color)
        return self


class PolygonStep(StepBase):
    op: Literal["polygon"]
    points: list[tuple[int, int]] = Field(..., min_length=3)
    fill: Optional[str] = Field(default=None)
    outline: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def _validate_colors(self) -> "PolygonStep":
        if self.fill is not None:
            self.fill = _validate_hex_color(self.fill)
        if self.outline is not None:
            self.outline = _validate_hex_color(self.outline)
        return self


class PixelsStep(StepBase):
    op: Literal["pixels"]
    points: list[tuple[int, int]] = Field(..., min_length=1)
    color: str = Field(...)

    @model_validator(mode="after")
    def _validate_color(self) -> "PixelsStep":
        self.color = _validate_hex_color(self.color)
        return self


class TextStep(StepBase):
    op: Literal["text"]
    x: int
    y: int
    value: str
    font: Optional[str] = None
    size: int = Field(8, ge=4, le=64)
    color: str = Field("#FFFFFF")

    @model_validator(mode="after")
    def _validate_color(self) -> "TextStep":
        self.color = _validate_hex_color(self.color)
        return self


class StepGroup(StepBase):
    op: Literal["group"]
    steps: list["CanvasStep"] = Field(default_factory=list)


CanvasStep = Annotated[
    RectStep | CircleStep | LineStep | PolygonStep | PixelsStep | TextStep | StepGroup,
    Field(discriminator="op"),
]


class CanvasSpec(BaseModel):
    """Canvas dimensions and defaults."""

    model_config = ConfigDict(extra="forbid")

    w: int = Field(..., ge=1)
    h: int = Field(..., ge=1)
    bg: str = Field("#202020")

    @model_validator(mode="after")
    def _validate_bg(self) -> "CanvasSpec":
        self.bg = _validate_hex_color(self.bg)
        return self


class TextDirective(BaseModel):
    """Fallback text rendering directive."""

    model_config = ConfigDict(extra="forbid")

    render_text: str
    duration_sec: Optional[int] = Field(default=None, ge=1)


class CanvasDocument(BaseModel):
    """Top-level Canvas DSL document."""

    model_config = ConfigDict(extra="forbid")

    version: str
    canvas: CanvasSpec
    caption: str
    palette: Optional[list[str]] = None
    seed: Optional[int] = None
    steps: Optional[list[CanvasStep]] = Field(default=None)
    render_text: Optional[str] = None
    duration_sec: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_payload(self) -> "CanvasDocument":
        has_steps = bool(self.steps)
        has_text = bool(self.render_text)

        if has_steps and has_text:
            raise ValueError("CanvasDocument cannot have both steps and render_text")
        if not has_steps and not has_text:
            raise ValueError("CanvasDocument must define steps or render_text")

        if self.palette:
            self.palette = [_validate_hex_color(color) for color in self.palette]

        if has_text and self.duration_sec is None:
            # Default to caller-managed duration (e.g., SHOW_DURATION_SEC)
            self.duration_sec = None

        return self


def ensure_canvas_document(data: dict) -> CanvasDocument:
    """Parse an arbitrary dict into a validated CanvasDocument."""

    try:
        return CanvasDocument.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - convenience helper
        raise ValueError("Invalid canvas document") from exc

