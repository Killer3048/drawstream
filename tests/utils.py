from __future__ import annotations

from draw_stream.config import LLMBackend, Settings


def make_settings(**overrides) -> Settings:
    data = {
        "DA_WS_URL": "https://example.com/connection/websocket",
        "DA_API_BASE": "https://example.com/api",
        "DA_ACCESS_TOKEN": "test-token",
        "DA_USER_ID": 123,
        "DA_REST_POLL_INTERVAL_SEC": 30,
        "QUEUE_MAX_SIZE": 8,
        "LLM_BACKEND": LLMBackend.OLLAMA.value,
        "LLM_ENDPOINT": "https://llm.example.com/v1/chat/completions",
        "LLM_MODEL_ID": "test-model",
        "LLM_TEMPERATURE": 0.1,
        "LLM_MAX_TOKENS": 256,
        "LLM_TIMEOUT_SEC": 5,
        "LLM_RETRY_ATTEMPTS": 0,
        "CANVAS_W": 96,
        "CANVAS_H": 96,
        "WINDOW_SCALE": 4,
        "FRAME_RATE": 30,
        "DEFAULT_STEP_DURATION_MS": 400,
        "SHOW_DURATION_SEC": 60,
        "API_HOST": "127.0.0.1",
        "API_PORT": 9000,
        "LOG_LEVEL": "INFO",
        "LOCALE": "en",
    }
    data.update(overrides)
    return Settings.model_validate(data)

