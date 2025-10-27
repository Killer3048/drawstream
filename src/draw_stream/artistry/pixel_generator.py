"""Pixel art generation via diffusers and pixel-art-xl LoRA."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import colorsys
from PIL import Image

try:  # pragma: no cover - heavy dependency
    import torch
    from diffusers import DiffusionPipeline
    from diffusers.utils import logging as diffusers_logging
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "PixelArtGenerator requires 'torch' and 'diffusers'. Please install the dependencies first."
    ) from exc

from ..config import Settings, get_settings
from ..models import SceneDescription

logger = logging.getLogger(__name__)


class PixelArtGeneratorError(RuntimeError):
    """Raised when pixel art generation fails."""


class PixelArtGenerator:
    """Wrapper over diffusers pipeline using pixel-art-xl LoRA."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        if self._settings.pixel_device.lower() != "cuda":
            raise RuntimeError("PixelArtGenerator is configured to run only on CUDA devices")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA device not detected. Ensure NVIDIA drivers and torch.cuda are available.")

        self._device = "cuda"
        dtype = torch.float16
        diffusers_logging.set_verbosity_error()
        logger.info(
            "pixel_generator.init",
            extra={
                "base": self._settings.pixel_model_base,
                "lora": self._settings.pixel_lora_repo,
                "device": self._device,
                "dtype": str(dtype),
            },
        )
        self._pipe = DiffusionPipeline.from_pretrained(
            self._settings.pixel_model_base,
            use_safetensors=True,
        )
        if hasattr(self._pipe, "load_lora_weights"):
            self._pipe.load_lora_weights(
                self._settings.pixel_lora_repo,
                weight_name=self._settings.pixel_lora_weight,
            )
        self._pipe.to(self._device, dtype=dtype)
        self._pipe.set_progress_bar_config(disable=True)

    async def generate(self, description: SceneDescription) -> Image.Image:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._generate_sync, description)

    def _generate_sync(self, description: SceneDescription) -> Image.Image:
        generator = None
        if description.seed is not None:
            generator = torch.Generator(device=self._device).manual_seed(description.seed)
        try:
            result = self._pipe(
                prompt=self._build_prompt(description),
                negative_prompt=description.negative_prompt,
                height=self._settings.pixel_height,
                width=self._settings.pixel_width,
                num_inference_steps=self._settings.pixel_num_inference_steps,
                guidance_scale=self._settings.pixel_guidance_scale,
                generator=generator,
            )
        except Exception as exc:  # pragma: no cover
            raise PixelArtGeneratorError("Diffusion inference failed") from exc

        if not result.images:
            raise PixelArtGeneratorError("Diffusion pipeline returned no images")
        return result.images[0]

    def _build_prompt(self, description: SceneDescription) -> str:
        prompt = self._trim_text(description.prompt, 48)
        extras = ["Pixel art illustration, crisp outlines, deliberate dithering, low parallax."]
        if description.style_notes:
            extras.append(self._trim_text(description.style_notes, 16))
        palette_hint = self._describe_palette(description.palette or [])
        if palette_hint:
            extras.append(palette_hint)
        combined = " ".join([prompt] + extras)
        return self._trim_text(combined, 72)

    @staticmethod
    def _trim_text(text: str | None, limit: int) -> str:
        if not text:
            return ""
        words = text.split()
        if len(words) <= limit:
            return text.strip()
        return " ".join(words[:limit]).strip()

    def _describe_palette(self, palette: list[str]) -> str:
        if not palette:
            return ""
        names = [self._hex_to_color_name(color) for color in palette[:4]]
        names = [name for name in names if name]
        if not names:
            return ""
        return "Palette hints: " + ", ".join(names)

    @staticmethod
    def _hex_to_color_name(value: str) -> str:
        value = value.lstrip("#")
        if len(value) != 6:
            return "rich tone"
        try:
            r = int(value[0:2], 16) / 255.0
            g = int(value[2:4], 16) / 255.0
            b = int(value[4:6], 16) / 255.0
        except ValueError:
            return "rich tone"

        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        hue = h * 360

        if v < 0.18:
            base = "inky black"
        elif v > 0.9 and s < 0.2:
            base = "paper white"
        elif s < 0.15:
            base = "soft gray"
        elif hue < 20 or hue >= 340:
            base = "crimson"
        elif hue < 45:
            base = "ember orange"
        elif hue < 70:
            base = "golden yellow"
        elif hue < 150:
            base = "emerald green"
        elif hue < 200:
            base = "teal"
        elif hue < 250:
            base = "azure blue"
        elif hue < 290:
            base = "violet"
        elif hue < 330:
            base = "magenta"
        else:
            base = "sunset red"

        if base in {"inky black", "paper white", "soft gray"}:
            return base

        if s > 0.7 and v > 0.7:
            prefix = "vibrant"
        elif v < 0.4:
            prefix = "dusky"
        else:
            prefix = "soft"
        return f"{prefix} {base}"
