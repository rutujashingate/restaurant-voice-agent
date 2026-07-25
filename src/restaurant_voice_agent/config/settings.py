"""Application settings loaded from the environment."""

from __future__ import annotations

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from restaurant_voice_agent.domain.enums import AppEnvironment, TTSProvider


class Settings(BaseSettings):
    """Typed environment settings for local and deployed runtimes."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    app_env: AppEnvironment = Field(default=AppEnvironment.DEVELOPMENT)
    log_level: str = Field(default="INFO")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1, le=65535)

    database_url: Optional[str] = None
    langgraph_database_url: Optional[str] = None
    redis_url: Optional[str] = None

    ollama_base_url: Optional[str] = Field(default="http://localhost:11434")
    llm_model: str = Field(default="qwen3:4b-instruct")
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    stt_model: str = Field(default="faster-whisper-small")
    stt_device: str = Field(default="cpu")
    stt_compute_type: str = Field(default="int8")

    tts_provider: TTSProvider = Field(default=TTSProvider.ELEVENLABS)
    eleven_api_key: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    elevenlabs_model: str = Field(default="eleven_flash_v2_5")

    livekit_url: Optional[str] = None
    livekit_api_key: Optional[str] = None
    livekit_api_secret: Optional[str] = None

    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    twilio_messaging_service_sid: Optional[str] = None
    human_escalation_phone: Optional[str] = None

    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_success_url: Optional[str] = None
    stripe_cancel_url: Optional[str] = None

    otel_exporter_otlp_endpoint: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: Optional[str] = None
