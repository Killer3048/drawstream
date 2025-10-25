# Architecture Overview

## Runtime Topology
- **DonationIngestor** listens to Donation Alerts via WebSocket (Centrifugo). On failure or startup fallback, it performs REST polling.
- **Gatekeeper** applies RU/EN NSFW heuristics. NSFW requests bypass the LLM and enqueue a `render_text: "You are too small"` directive.
- **WorkQueue** is a strict FIFO implemented with `asyncio.Queue` and an auxiliary deque for HUD previews. Concurrency is limited to a single renderer worker.
- **LLM Orchestrator** вызывает локальный OpenAI-совместимый эндпоинт Ollama (модель `qwen2.5-coder:14b-instruct-q4_K_M`, 4-битное квантование), чтобы получить Canvas-DSL в формате JSON.
- **Renderer** (pygame) interprets the DSL, animates drawing on a 96×96 surface, and upscales via nearest-neighbor into the display window. It renders HUD elements, queue status, and the caption "All for you".
- **Control API** (FastAPI) exposes health, queue introspection, skip, and clear operations. WebSocket notifications broadcast status updates for operator tooling.

## Module Layout
```
src/draw_stream/
  __init__.py
  config.py            # Pydantic BaseSettings for env-driven config
  logging.py           # Structured logging bootstrap
  models.py            # Shared dataclasses/pydantic models for donations & tasks
  gatekeeper.py        # Keyword/regex-based NSFW filter
  llm.py               # OpenAI-compatible client, response validation, retries
  canvas_dsl.py        # Pydantic schema + helpers for Canvas-DSL
  donation/
    __init__.py
    websocket.py       # Centrifugo subscription client
    rest.py            # REST polling fallback client
    ingestor.py        # Coordination, reconnection, fan-out into queue
  queue.py             # FIFO manager with preview deque & metrics hooks
  renderer/
    __init__.py
    surface.py         # Low-level pygame surface helpers (96×96)
    animations.py      # Stroke, fill, pixel_reveal implementations
    hud.py             # HUD layout, text rendering, timers, queue overlay
    runtime.py         # Renderer lifecycle and main coroutine
  api/
    __init__.py
    server.py          # FastAPI app + background tasks integration
  app.py               # Application bootstrap & lifecycle management
  main.py              # CLI entry point (asyncio.run(app.main()))
```

## Data Model
- **DonationEvent**: normalized payload (`id`, `donor`, `message`, `amount`, `currency`, `timestamp`).
- **RenderTask**: includes event metadata, gatekeeper status, and either `RenderInstruction` (canvas DSL) or sentinel for fallback text.
- **CanvasPlan** (`CanvasDSLDocument`): top-level DSL object with schema validation and deterministic defaults (seed, durations).
- **RendererState**: shared across HUD & API; tracks active task, queue preview, timers, and FPS metrics.

## Control Flow
1. Ingestor pushes `DonationEvent` into `QueueManager.enqueue_request`.
2. Worker pulls next request, applies gatekeeper, triggers orchestrator if needed, then passes a validated `CanvasPlan` to the renderer.
3. Renderer animates all steps sequentially, enforcing per-step animation metadata. Upon completion, it holds the final frame for `SHOW_DURATION_SEC` (~90s) before acknowledging completion.
4. During idle/hold periods, HUD shows countdown timer and queue preview. Queue remains blocked while the hold timer runs.
5. Operator actions (skip/clear) manipulate the queue via `QueueManager` APIs exposed through FastAPI, signalling renderer where appropriate.

## Reliability Considerations
- **Resilience**: WebSocket client automatically reconnects with exponential backoff; REST polling runs periodically when WS unavailable.
- **LLM Robustness**: HTTPX client enforces low temperature, timeouts, retries with jitter. Responses validated against DSL schema; invalid JSON downgraded to fallback text with logged error.
- **Renderer Safety**: `RendererRuntime` catches exceptions per step, logs, and displays fallback notification overlay.
- **Shutdown**: Graceful cancellation of ingest, worker, renderer, and API tasks; cleans up HTTP clients and pygame resources.

## Configuration Keys
Environment variables (loaded via `python-dotenv`):
- Donation Alerts: `DA_WS_URL`, `DA_API_URL`, `DA_CLIENT_ID`, `DA_CLIENT_SECRET`, `DA_ACCESS_TOKEN`, `DA_USER_ID`, `DA_REST_POLL_INTERVAL_SEC`.
- LLM: `LLM_BACKEND`, `LLM_ENDPOINT`, `LLM_MODEL_ID`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT_SEC`.
- Renderer: `CANVAS_W`, `CANVAS_H`, `WINDOW_SCALE`, `FRAME_RATE`, `DEFAULT_STEP_DURATION_MS`, `SHOW_DURATION_SEC`.
- API: `API_HOST`, `API_PORT`.
- Misc: `LOG_LEVEL`, `LOCALE`.

## HUD Composition
- Left column: current donor name, amount/currency, message (wrapped), progress bar for drawing/hold phases.
- Right column: "Next up" list (up to 5 queued donors/messages) with ETA estimates based on configured durations.
- Bottom banner: static caption **All for you** aligned centered.
- Top-right: queue length counter + FPS rolling average.

## Testing Strategy
- Unit tests for gatekeeper regex coverage, DSL validation, and orchestrator fallback handling.
- Property-style tests for DSL parser (round-tripping known-good plans).
- Renderer tests focus on deterministic timeline calculations (run headless via pygame SDL dummy video driver).
- Integration test for queue worker orchestrating gatekeeper + fallback DSL.
