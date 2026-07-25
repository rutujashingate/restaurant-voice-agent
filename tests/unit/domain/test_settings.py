"""Tests for settings parsing and optional provider values."""

from restaurant_voice_agent.config.settings import Settings
from restaurant_voice_agent.domain.enums import AppEnvironment, TTSProvider

SETTINGS_ENV_VARS = [
    "APP_ENV",
    "LOG_LEVEL",
    "API_HOST",
    "API_PORT",
    "DATABASE_URL",
    "LANGGRAPH_DATABASE_URL",
    "REDIS_URL",
    "OLLAMA_BASE_URL",
    "LLM_MODEL",
    "LLM_TEMPERATURE",
    "STT_MODEL",
    "STT_DEVICE",
    "STT_COMPUTE_TYPE",
    "TTS_PROVIDER",
    "ELEVEN_API_KEY",
    "ELEVENLABS_VOICE_ID",
    "ELEVENLABS_MODEL",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "TWILIO_MESSAGING_SERVICE_SID",
    "HUMAN_ESCALATION_PHONE",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_SUCCESS_URL",
    "STRIPE_CANCEL_URL",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
]


def _clear_settings_env(monkeypatch) -> None:
    for env_var in SETTINGS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_settings_loads_optional_provider_values_without_env(monkeypatch) -> None:
    _clear_settings_env(monkeypatch)

    settings = Settings()

    assert settings.app_env == AppEnvironment.DEVELOPMENT
    assert settings.api_host == "0.0.0.0"
    assert settings.tts_provider == TTSProvider.ELEVENLABS
    assert settings.database_url is None
    assert settings.eleven_api_key is None


def test_settings_parses_environment_overrides(monkeypatch) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TTS_PROVIDER", "kokoro")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.5")
    monkeypatch.setenv("API_PORT", "9000")

    settings = Settings()

    assert settings.app_env == AppEnvironment.TEST
    assert settings.tts_provider == TTSProvider.KOKORO
    assert settings.llm_temperature == 0.5
    assert settings.api_port == 9000
