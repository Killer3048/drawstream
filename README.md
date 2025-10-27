# Draw Stream

Interactive donation-driven pixel art pipeline for live streaming. Ollama (Qwen 2.5 Coder 14B) interprets donations and crafts prompts, while `nerijs/pixel-art-xl` (SDXL LoRA) renders the actual pixel art that we replay through a deterministic Canvas-DSL animation.

## Features
- Donation Alerts ingestion via Centrifugo WebSocket with REST polling fallback
- NSFW gatekeeper that downgrades unsafe requests to a static "You are too small" card
- Deterministic Canvas-DSL interpreted by a pygame renderer with pixel-by-pixel animation
- Faux brush-stroke animation that replays the SDXL output stroke-by-stroke on a 1080p layout
- HUD overlay displaying current job, queue preview, timers, caption, and FPS
- FastAPI control panel: health, queue snapshot, skip, and clear operations
- Structured logging, environment-driven configuration, and graceful shutdown
- Dual-stage art generation: scene planner (Ollama) + SDXL LoRA `nerijs/pixel-art-xl`, with automatic image-to-DSL conversion
- Reference Canvas-DSL example (`assets/examples/aurora_cabin_plan.json`) + render script for QA (`tests/manual/create_reference_plan.py`)

## Prerequisites
- **OS**: Windows 11 with WSL2 Ubuntu 24.04 and WSLg enabled (for pygame window forwarding)
- **Python**: 3.11.x (managed by Poetry virtual environment)
- **System packages** (Ubuntu):
  ```bash
  sudo apt update
  sudo apt install python3.11-dev python3.11-venv build-essential \
       libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev libsdl2-gfx-dev \
       libportmidi-dev libfreetype6-dev
  ```
- **Donation Alerts OAuth**: client credentials with `oauth-user-show`, `oauth-donation-subscribe`, and `oauth-donation-index` scopes
- **Local LLM backend**: Ollama с моделью `qwen2.5-coder:14b-instruct-q4_K_M` (4-битное квантование)
- **Pixel diffusion stack**: см. раздел "Offline Weights" ниже.
- **Pixel diffusion stack**: PyTorch 2.1+ CUDA 11.8, `diffusers>=0.29`, `transformers>=4.44`, `safetensors`, `xformers`, `scikit-image` (используется для обработки изображений). Перед запуском установите как минимум:
  ```bash
  pip install torch==2.1.2+cu118 torchvision==0.16.2+cu118 --extra-index-url https://download.pytorch.org/whl/cu118
  pip install diffusers==0.29.0 transformers==4.44.2 safetensors==0.4.4 scikit-image==0.24.0
  ```

## Installation
```bash
poetry install --with dev
```
All runtime commands below assume the Poetry environment is activated (e.g., `poetry shell` or the provided virtualenv at `/home/vem/.cache/pypoetry/virtualenvs/draw-stream-*/bin/activate`).

## Environment Configuration
Create a `.env` file in the project root and populate the following keys. Defaults are shown where applicable.

| Variable | Description | Default |
|----------|-------------|---------|
| `DA_WS_URL` | Donation Alerts Centrifugo WebSocket endpoint | `https://centrifugo.donationalerts.com/connection/websocket` |
| `DA_API_BASE` | Donation Alerts REST API base | `https://www.donationalerts.com/api/v1` |
| `DA_ACCESS_TOKEN` | OAuth access token with required scopes | _required_ |
| `DA_USER_ID` | Donation Alerts numeric user ID | optional |
| `DA_REST_POLL_INTERVAL_SEC` | REST polling interval (fallback) | `30` |
| `QUEUE_MAX_SIZE` | Max queued donations | `32` |
| `LLM_BACKEND` | Which orchestrator to use (`ollama`, etc.) | `ollama` |
| `LLM_ENDPOINT` | OpenAI-compatible chat completions endpoint | `http://127.0.0.1:11434/v1/chat/completions` |
| `LLM_MODEL_ID` | Local model served via Ollama | `qwen2.5-coder:14b-instruct-q4_K_M` |
| `LLM_TEMPERATURE` | Sampling temperature | `0.1` |
| `LLM_MAX_TOKENS` | Max generated tokens | `1536` |
| `LLM_TIMEOUT_SEC` | HTTP timeout for LLM requests | `30` |
| `LLM_RETRY_ATTEMPTS` | Max retries for LLM failures | `3` |
| `PIXEL_MODEL_BASE` | SDXL base checkpoint | `stabilityai/stable-diffusion-xl-base-1.0` |
| `PIXEL_LORA_REPO` | LoRA repo (local folder or HF id) | `nerijs/pixel-art-xl` |
| `PIXEL_LORA_WEIGHT` | Weight filename | `pixel-art-xl.safetensors` |
| `PIXEL_DEVICE` | Torch device | `cuda` |
| `PIXEL_HEIGHT`/`PIXEL_WIDTH` | Diffusion canvas size | `768` |
| `PIXEL_INFERENCE_STEPS` | Number of diffusion steps | `40` |
| `PIXEL_GUIDANCE` | CFG guidance scale | `5.0` |
| `PIXEL_OUTPUT_SIZE` | Downscaled Canvas-DSL size | `96` |
| `PIXEL_PALETTE_COLORS` | Palette limit for quantization | `12` |
| `PIXEL_STROKE_CHUNK` | Pixels per faux brush stroke | `220` |
| `PIXEL_ANIMATION_BASE_MS` | Base duration per stroke | `450` |
| `PIXEL_ANIMATION_PER_PX_MS` | Additional ms per pixel | `2` |
| `PIXEL_ANIMATION_DELAY_MS` | Delay between successive strokes | `70` |
| `CANVAS_W`/`CANVAS_H` | Base canvas resolution | `96` |
| `WINDOW_SCALE` | Preferred art upscale factor | `8` |
| `DISPLAY_WIDTH`/`DISPLAY_HEIGHT` | Final pygame window size | `1920` / `1080` |
| `FRAME_RATE` | Target renderer FPS | `60` |
| `DEFAULT_STEP_DURATION_MS` | Default per-step animation duration | `700` |
| `SHOW_DURATION_SEC` | Hold time after drawing completes | `90` |
| `API_HOST` / `API_PORT` | FastAPI bind address | `0.0.0.0` / `8080` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOCALE` | Locale hints for the LLM | `en` |

## Offline Weights
1. Запустите `tar -xzf sdxl_bundle.tar.gz` в корне проекта. Появятся директории `sdxl-base/` (готовая SDXL-пайплайн с fp16 VAE) и `pixel-art-xl/` (LoRA вес `pixel-art-xl.safetensors`).
2. Убедитесь, что `.env` указывает на локальные пути (например, `PIXEL_MODEL_BASE=sdxl-base`, `PIXEL_LORA_REPO=pixel-art-xl`).
3. Если веса лежат в другом месте, обновите пути или добавьте симлинки. Важна структура diffusers (UNet, text encoders, vae, scheduler, tokenizer).
4. После распаковки можно удалить архив, он игнорируется `.gitignore`.

## Running the Service
```bash
poetry run python -m draw_stream.main
```
This launches:
1. Donation ingestion (WebSocket + REST fallback)
2. Render worker and pygame window via WSLg
3. FastAPI control panel on `http://API_HOST:API_PORT`

### Control API
- `GET /health` – health probe
- `GET /queue` – active job plus next five queue entries
- `POST /queue/skip` – skip the current render (sets `SkipRequested`)
- `POST /queue/clear` – drop queued donations while preserving the active job

## Renderer & Canvas-DSL
- Canvas-DSL describes drawing primitives (`rect`, `circle`, `line`, `polygon`, `pixels`, `text`, `group`) and animation metadata (`stroke`, `fill`, `pixel_reveal`, delays, duration).
- Plans produced by the LLM are validated via `pydantic` to guarantee deterministic playback.
- When the NSFW gatekeeper fires or the LLM fails, the renderer displays a text-only scene with the message `You are too small` for `SHOW_DURATION_SEC` seconds.
- HUD overlay: active donor info, request message, progress bar, queue preview, FPS indicator, and caption “All for you”. The pygame window is fixed at 1080p (configurable) with the animated canvas on the left and the translucent HUD panel on the right so OBS can capture a ready-to-stream composition.

## LLM + Pixel Backend
- Установите [Ollама](https://ollama.com). После установки выполните:
  ```bash
  ollama pull qwen2.5-coder:14b-instruct-q4_K_M
  ollama serve
  ```
  Сервер по умолчанию слушает `127.0.0.1:11434`.
- Убедитесь, что OpenAI-совместимый эндпоинт активен и модель действительно в квантовании Q4:
  ```bash
  curl http://127.0.0.1:11434/v1/models
  ollama show qwen2.5-coder:14b-instruct-q4_K_M | grep quantization
  ```
- Scene Planner (Ollama) выдаёт JSON с prompt/negative prompt/палитрой.
- Pixel Generator (`pixel-art-xl`) запускается через `diffusers`; LoRA автоматически подмешивается поверх SDXL.
- Модуль `ImageToCanvas` уменьшает результат до 96×96, квантует палитру и создаёт Canvas-DSL шаги с псевдо-анимацией.

## Streaming Integration
1. In Windows, configure OBS Studio to capture the WSLg pygame window via *Window Capture*.
2. Add overlays, audio sources, and restream settings for Twitch + TikTok (RTMP keys managed per platform).
3. Keep the pygame window visible/on top to ensure consistent capture.

## Testing & Quality
```bash
poetry run pytest
```
The suite covers gatekeeper heuristics, Canvas-DSL validation, queue semantics, and LLM orchestrator fallback behaviour.

Linting (optional but recommended):
```bash
poetry run ruff check
poetry run mypy src
```

## Reference Assets
- `assets/examples/aurora_cabin_plan.json` — вручную собранный Canvas-DSL с многоуровневым планом сцены «Aurora Cabin».
- `tests/manual/create_reference_plan.py` — генерирует JSON и PNG (`out/reference/aurora_cabin_reference.png`) из эталонного плана.
- `tests/manual/render_samples.py` — использует текущую LLM, чтобы сохранять PNG предпросмотры донатов в `out/render_samples/` (для ревью качества).
- `tests/manual/scene_planner_probe.py` — прогоняет ~10 разнообразных донатов через ScenePlanner и сохраняет ответы в `out/scene_planner_probe/` для ручного ревью.

## Shutdown
Press `Ctrl+C` in the terminal; the service gracefully closes WebSocket/HTTP clients, waits for the current render to finish (unless skipped), and shuts down pygame/WSLg resources.

## Additional Docs
- `docs/ARCHITECTURE.md` – detailed component topology, data flow, and HUD design.
