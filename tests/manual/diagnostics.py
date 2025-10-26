"""Diagnostics tool: per-donation asset dump (scene, image, layers, animation)."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src"))

from PIL import Image, ImageColor

from draw_stream.artistry.scene_planner import ScenePlanner
from draw_stream.artistry.pixel_generator import PixelArtGenerator
from draw_stream.artistry.image_to_canvas import ImageToCanvas
from draw_stream.models import DonationEvent

OUTPUT_ROOT = Path("diagnostics")
OLLAMA_MODEL = "qwen2.5-coder:14b-instruct-q4_K_M"
SAMPLES = [
    (
        "cyberpunk_dragon",
        "Massive tip! Paint an isometric cyberpunk dragon shredding a neon guitar on a rain soaked rooftop with holographic city behind and acid-green lightning",
    ),
    (
        "aurora_cabin",
        "Please draw a peaceful winter cabin with aurora sky, smoke from chimney and warm window lights while a fox watches in the snow",
    ),
    (
        "robot_cafe",
        "Pixel art request: donut-shaped robot serving coffee to tiny cats in a pastel cafe full of plants and fairy lights",
    ),
    (
        "skywhale_post",
        "Mega donor! Render a gentle sky-whale delivering mail between floating islands with streams of letters trailing behind",
    ),
    (
        "witch_market",
        "Night market for witches with potion stalls, lantern fog, and curious familiars peeking over cauldrons",
    ),
    (
        "starship_kitchen",
        "Chef cooking ramen in zero gravity aboard a research starship, ingredients floating in glowing bowls",
    ),
]


def make_event(slug: str, message: str) -> DonationEvent:
    return DonationEvent(
        id=slug,
        donor="Diagnostics",
        message=message,
        amount="42.00",
        currency="USD",
        timestamp="2024-01-01T00:00:00+00:00",
    )


async def main() -> None:
    args = parse_args()
    selected = [s for s in SAMPLES if not args.only or s[0] in args.only]
    if not selected:
        print("No samples to run")
        return

    OUTPUT_ROOT.mkdir(exist_ok=True)
    stop_llm_model()
    clear_cuda_cache()

    scene_planner = ScenePlanner()
    pixel_gen = PixelArtGenerator()
    builder = ImageToCanvas()

    try:
        for slug, message in selected:
            print(f"Processing {slug}...")
            await process_sample(slug, message, scene_planner, pixel_gen, builder)
            stop_llm_model()
            clear_cuda_cache()
    finally:
        await scene_planner.aclose()


def prepare_folder(slug: str) -> tuple[Path, Path, Path]:
    folder = OUTPUT_ROOT / slug
    if folder.exists():
        shutil.rmtree(folder)
    frames_dir = folder / "frames"
    layers_dir = folder / "layers"
    folder.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    layers_dir.mkdir(parents=True, exist_ok=True)
    return folder, frames_dir, layers_dir


async def process_sample(
    slug: str,
    message: str,
    scene_planner: ScenePlanner,
    pixel_gen: PixelArtGenerator,
    builder: ImageToCanvas,
) -> None:
    event = make_event(slug, message)
    try:
        scene = await scene_planner.describe(event)
    except Exception as exc:
        print(f"Scene planner failed for {slug}: {exc}")
        return

    stop_llm_model()
    clear_cuda_cache()

    image = await pixel_gen.generate(scene)
    doc, layers = builder.build_with_debug(image)
    folder, frames_dir, layers_dir = prepare_folder(slug)

    (folder / "scene.json").write_text(scene.model_dump_json(indent=2))
    (folder / "canvas.json").write_text(doc.model_dump_json(indent=2))
    image.save(folder / "pixel.png")
    image.resize((doc.canvas.w, doc.canvas.h), Image.NEAREST).save(folder / "pixel_downsampled.png")

    if layers:
        for idx, layer in enumerate(layers):
            (layers_dir / f"layer_{idx:02d}.json").write_text(json.dumps(layer, indent=2))

    save_animation_frames(doc, frames_dir)


def save_animation_frames(doc, frames_dir: Path) -> None:
    width, height = doc.canvas.w, doc.canvas.h
    bg = ImageColor.getrgb(doc.canvas.bg)
    current = Image.new("RGB", (width, height), bg)

    def apply_step(step) -> None:
        if step.op == "pixels":
            color = ImageColor.getrgb(step.color)
            for x, y in step.points:
                current.putpixel((x, y), color)
        elif step.op == "rect" and step.fill:
            color = ImageColor.getrgb(step.fill)
            for x in range(step.x, step.x + step.w):
                for y in range(step.y, step.y + step.h):
                    current.putpixel((x, y), color)

    for idx, step in enumerate(doc.steps or []):
        apply_step(step)
        upscaled = current.resize((width * 4, height * 4), Image.NEAREST)
        upscaled.save(frames_dir / f"frame_{idx:02d}.png")


def parse_args():
    parser = argparse.ArgumentParser(description="Diagnostics asset dump")
    parser.add_argument("--only", nargs="*", help="limit to specific sample slugs")
    return parser.parse_args()


def stop_llm_model() -> None:
    try:
        subprocess.run(["ollama", "stop", OLLAMA_MODEL], check=False)
    except FileNotFoundError:
        pass


def clear_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
