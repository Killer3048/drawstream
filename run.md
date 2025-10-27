# Runbook

These steps assume `.env` is already filled with valid Donation Alerts credentials and paths to the local SDXL/LoRA weights.

## 1. Environment & Dependencies
1. Install system deps (SDL2, fonts, etc.) as described in `README.md`.
2. Install project deps and activate the Poetry venv:
   ```bash
   poetry install --with dev
   source $(poetry env info --path)/bin/activate
   ```
3. Ensure CUDA toolkits and PyTorch w/ GPU wheels are installed (torch 2.1+ w/ cu118 per README).

## 2. Services to Start
1. **Donation Alerts**: no local service; just ensure the token in `.env` is valid.
2. **Ollama** (LLM):
   ```bash
   ollama pull qwen2.5-coder:14b-instruct-q4_K_M
   ollama serve
   ```
   The endpoint must match `LLM_ENDPOINT`.

## 3. Pre-flight VRAM Ritual (run whenever diffusers will start)
```bash
ollama stop qwen2.5-coder:14b-instruct-q4_K_M
python - <<'PY'
import torch
if torch.cuda.is_available():
    torch.cuda.empty_cache()
PY
```
This frees GPU memory before SDXL spins up. The art pipeline also repeats this automatically between LLM and diffusion, but doing it manually before diagnostics/smoke tests avoids OOMs.

## 4. Launch the Stream Pipeline
```bash
python main.py
```
What happens:
- Donation Alerts WebSocket + REST fallback begin ingesting donations.
- ScenePlanner (Ollama) judges every request (PG-13 policy: erotica/nudity is rejected, tasteful swimwear ok) and only approved prompts reach SDXL.
- SDXL + pixel-art postprocessing + Canvas converter run inside the worker.
- Pygame opens a 1920×1080 window (use WSLg/OBS Window Capture).
- FastAPI control panel serves on `http://API_HOST:API_PORT` (see `/health`, `/queue`, `/queue/skip`, `/queue/clear`).

Keep the SDL window visible for OBS. The HUD shows the active donor card, queue list, LIVE badge, and timers.

### Console test donations
While `python main.py` is running you can type commands in the same terminal:

- `donate <amount> <message>` — manual test (e.g. `donate 7.5 Draw a cyber dragon`).
- `da <amount> <message>` — simulates a Donation Alerts payload (donor labeled `DonationAlerts(Test)`).
- `quit` / `exit` — stop the app.

Все консольные донаты проходят тот же пайплайн (gatekeeper → LLM → SDXL → Canvas → HUD).

## 5. Smoke / Manual Checks
Run these commands (after the VRAM ritual) to verify major components:

### Donation Alerts Connectivity
```bash
PYTHONPATH=src python - <<'PY'
import asyncio
from draw_stream.donation.rest import DonationAlertsRESTClient
async def main():
    client = DonationAlertsRESTClient()
    try:
        events = list(await client.fetch_latest(limit=3))
    finally:
        await client.aclose()
    print(events)
asyncio.run(main())
PY
```
WebSocket probe:
```bash
PYTHONPATH=src python - <<'PY'
import asyncio
from draw_stream.donation.websocket import DonationAlertsWebSocket
async def main():
    ws = DonationAlertsWebSocket()
    iterator = ws._run_once()
    try:
        await asyncio.wait_for(iterator.__anext__(), timeout=2)
    except asyncio.TimeoutError:
        print('Subscribed OK (no events yet)')
    finally:
        await iterator.aclose()  # type: ignore
asyncio.run(main())
PY
```

### LLM Scene Planner Probe
```bash
PYTHONPATH=src python tests/manual/scene_planner_probe.py
```
Writes JSON outputs to `out/scene_planner_probe/` for 10 sample donations.

### Pixel Art Diagnostics
```bash
# run VRAM ritual first
python tests/manual/diagnostics.py --only skywhale_post witch_market starship_kitchen
```
Generates `diagnostics/<slug>/` folders with `scene.json`, `pixel.png`, `canvas.json`, layers, and animation frames.

### Render Samples (SDL dummy preview)
```bash
# run VRAM ritual first
python tests/manual/render_samples.py
```
Saves PNG previews under `out/render_samples/`.

### Full App Smoke (headless)
```bash
SDL_VIDEODRIVER=dummy SHOW_DURATION_SEC=5 PYTHONPATH=src python - <<'PY'
import asyncio, time
from datetime import datetime, timezone
from draw_stream.app import DrawStreamApp
from draw_stream.models import DonationEvent

async def drive():
    app = DrawStreamApp()
    await app.start()
    try:
        for slug, message in [("smoke1", "Aurora cabin"), ("smoke2", "Witch market")]:
            await app._donation_queue.put(DonationEvent(
                id=slug,
                donor="Smoke",
                message=message,
                amount="5",
                currency="USD",
                timestamp=datetime.now(timezone.utc)
            ))
        await app._donation_queue.join()
        start = time.monotonic()
        while time.monotonic() - start < 90:
            queue_size = await app._render_queue.size()
            snapshot = app._renderer.snapshot()
            if queue_size == 0 and snapshot.active_task is None:
                break
            await asyncio.sleep(1)
    finally:
        await app.stop()

asyncio.run(drive())
PY
```

## 6. Unit Tests
```bash
poetry run pytest
```
Covers Canvas DSL validation, gatekeeper, image quantization, and queue logic.

Stick to this order (env ➝ services ➝ VRAM ritual ➝ runtime/tests) and every component—Donation Alerts, LLM, SDXL, animation, and the OBS-ready pygame window—runs as expected.
