"""Application configuration models and helpers."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import AnyHttpUrl, AnyUrl, Field, SecretStr, computed_field
from pydantic.functional_validators import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    """Supported logging levels."""

    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class LLMBackend(str, Enum):
    """Available LLM backends."""

    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    VLLM = "vllm"
    TGI = "tgi"


class Settings(BaseSettings):
    """Environment-driven application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Donation Alerts
    da_ws_url: AnyUrl = Field(..., alias="DA_WS_URL")
    da_api_base: AnyHttpUrl = Field(..., alias="DA_API_BASE")
    da_access_token: SecretStr = Field(..., alias="DA_ACCESS_TOKEN")
    da_user_id: Optional[int] = Field(None, alias="DA_USER_ID")
    da_rest_poll_interval_sec: int = Field(30, alias="DA_REST_POLL_INTERVAL_SEC")

    # Queue
    queue_max_size: int = Field(32, alias="QUEUE_MAX_SIZE")

    # LLM configuration
    llm_backend: LLMBackend = Field(LLMBackend.OLLAMA, alias="LLM_BACKEND")
    llm_endpoint: AnyHttpUrl = Field(..., alias="LLM_ENDPOINT")
    llm_model_id: str = Field(..., alias="LLM_MODEL_ID")
    llm_temperature: float = Field(0.1, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(1536, alias="LLM_MAX_TOKENS")
    llm_timeout_sec: float = Field(30.0, alias="LLM_TIMEOUT_SEC")
    llm_retry_attempts: int = Field(3, alias="LLM_RETRY_ATTEMPTS")

    # Renderer
    canvas_w: int = Field(96, alias="CANVAS_W")
    canvas_h: int = Field(96, alias="CANVAS_H")
    window_scale: int = Field(8, alias="WINDOW_SCALE")
    display_width: int = Field(2400, alias="DISPLAY_WIDTH")
    display_height: int = Field(1350, alias="DISPLAY_HEIGHT")
    frame_rate: int = Field(60, alias="FRAME_RATE")
    default_step_duration_ms: int = Field(700, alias="DEFAULT_STEP_DURATION_MS")
    show_duration_sec: int = Field(90, alias="SHOW_DURATION_SEC")
    pixel_model_base: str = Field(
        "stabilityai/stable-diffusion-xl-base-1.0", alias="PIXEL_MODEL_BASE"
    )
    pixel_lora_repo: str = Field("nerijs/pixel-art-xl", alias="PIXEL_LORA_REPO")
    pixel_lora_weight: str = Field("pixel-art-xl.safetensors", alias="PIXEL_LORA_WEIGHT")
    pixel_device: str = Field("cuda", alias="PIXEL_DEVICE")
    pixel_height: int = Field(768, alias="PIXEL_HEIGHT")
    pixel_width: int = Field(768, alias="PIXEL_WIDTH")
    pixel_num_inference_steps: int = Field(40, alias="PIXEL_INFERENCE_STEPS")
    pixel_guidance_scale: float = Field(5.0, alias="PIXEL_GUIDANCE")
    pixel_output_size: int = Field(96, alias="PIXEL_OUTPUT_SIZE")
    pixel_palette_colors: int = Field(12, alias="PIXEL_PALETTE_COLORS")
    pixel_stroke_chunk_size: int = Field(220, alias="PIXEL_STROKE_CHUNK")
    pixel_animation_base_duration_ms: int = Field(450, alias="PIXEL_ANIMATION_BASE_MS")
    pixel_animation_per_pixel_ms: int = Field(2, alias="PIXEL_ANIMATION_PER_PX_MS")
    pixel_animation_delay_ms: int = Field(70, alias="PIXEL_ANIMATION_DELAY_MS")

    # API
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8080, alias="API_PORT")

    # Misc
    log_level: LogLevel = Field(LogLevel.INFO, alias="LOG_LEVEL")
    locale: str = Field("en", alias="LOCALE")
    display_currency: str = Field("USD", alias="DISPLAY_CURRENCY")

    @computed_field(return_type=dict[str, str])
    def llm_headers(self) -> dict[str, str]:
        """Headers to use for LLM HTTP requests."""

        if self.llm_backend in {LLMBackend.OLLAMA, LLMBackend.LLAMACPP, LLMBackend.VLLM, LLMBackend.TGI}:
            return {"Content-Type": "application/json"}
        return {}

    @field_validator(
        "da_rest_poll_interval_sec",
        "queue_max_size",
        "llm_max_tokens",
        "canvas_w",
        "canvas_h",
        "window_scale",
        "frame_rate",
        "default_step_duration_ms",
        "show_duration_sec",
        "pixel_height",
        "pixel_width",
        "pixel_num_inference_steps",
        "pixel_output_size",
        "pixel_palette_colors",
        "pixel_stroke_chunk_size",
        "pixel_animation_base_duration_ms",
        "pixel_animation_per_pixel_ms",
        "pixel_animation_delay_ms",
        "api_port",
        "display_width",
        "display_height",
    )
    @classmethod
    def _ensure_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Value must be positive")
        return value

    @field_validator("llm_retry_attempts")
    @classmethod
    def _ensure_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Retry attempts must be non-negative")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
