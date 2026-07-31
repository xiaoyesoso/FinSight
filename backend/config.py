"""Application configuration for the IIRAS backend.

Loads settings from environment variables (optionally backed by a `.env` file)
and validates that every required variable is present. The backend fails fast
on startup if any required variable is missing so misconfigurations are caught
early instead of surfacing as cryptic runtime errors mid-run.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

# Load variables from a local .env file if present (no error if missing).
load_dotenv()

# Mandatory disclaimer surfaced in every research result.
DISCLAIMER = "本工具仅供学习和研究使用，不构成投资建议。股市有风险，投资需谨慎。"


@dataclass(frozen=True)
class Settings:
    """Typed view of the runtime configuration."""

    # Anthropic-compatible endpoint (Volcengine ARK, MiniMax, etc.).
    anthropic_base_url: str
    anthropic_model: str
    # API key for the LLM endpoint. We accept either ANTHROPIC_API_KEY
    # (standard) or MINIMAX_API_KEY (legacy) from the reference script.
    api_key: str
    # Bocha AI web-search key (optional; news/risk SubAgents need it).
    bocha_api_key: str
    # CORS origin for the frontend.
    frontend_origin: str
    # Directory used to store uploaded PDFs.
    upload_dir: str
    # OpenTelemetry (optional, opt-in). When the endpoint is unset, telemetry
    # is disabled entirely (build_otel_env returns {}).
    otel_exporter_otlp_endpoint: str
    otel_exporter_otlp_headers: str

    def apply_to_env(self) -> None:
        """Push settings back into os.environ so claude_agent_sdk picks them up.

        The SDK reads ANTHROPIC_* env vars directly, so we mirror the values
        here to keep a single source of truth in this dataclass.
        """
        os.environ.setdefault("ANTHROPIC_BASE_URL", self.anthropic_base_url)
        os.environ.setdefault("ANTHROPIC_MODEL", self.anthropic_model)
        # The SDK accepts either ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN.
        os.environ.setdefault("ANTHROPIC_API_KEY", self.api_key)
        os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", self.api_key)
        # Default model aliases - only set if not already configured in .env
        # (the user may have specific haiku/sonnet/opus model overrides).
        os.environ.setdefault("ANTHROPIC_DEFAULT_HAIKU_MODEL", self.anthropic_model)
        os.environ.setdefault("ANTHROPIC_DEFAULT_SONNET_MODEL", self.anthropic_model)
        os.environ.setdefault("ANTHROPIC_DEFAULT_OPUS_MODEL", self.anthropic_model)


def validate_settings() -> Settings:
    """Build a Settings instance and fail fast if required vars are missing.

    Exits the process with a clear message when a required variable is absent,
    which is far friendlier than a deep stack trace inside the agent run.
    """
    # The LLM API key may be provided as ANTHROPIC_API_KEY (standard) or
    # MINIMAX_API_KEY (legacy from the reference script). Prefer the former.
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("MINIMAX_API_KEY")

    required = {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL"),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL"),
        "ANTHROPIC_API_KEY or MINIMAX_API_KEY": api_key,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        # Fail fast with an actionable message.
        print(
            "[config] Missing required environment variables: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "[config] Copy backend/.env.example to backend/.env and fill in values.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Bocha API key is optional but recommended for news/risk SubAgents.
    bocha_key = os.getenv("BOCHA_API_KEY", "")
    if not bocha_key:
        print(
            "[config] Warning: BOCHA_API_KEY is not set. "
            "Web search will fail for news/risk SubAgents.",
            file=sys.stderr,
        )

    # Resolve the upload directory relative to the backend package so it
    # lives at backend/data/uploads/ (stable regardless of cwd).
    upload_dir = os.path.join(os.path.dirname(__file__), "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # CLI config dir inside the project so the Trae IDE sandbox doesn't block
    # session file reads/writes (which happens when using ~/.claude/).
    claude_config_dir = os.path.join(os.path.dirname(__file__), "data", "claude_config")
    os.makedirs(claude_config_dir, exist_ok=True)
    os.environ["CLAUDE_CONFIG_DIR"] = claude_config_dir

    settings = Settings(
        anthropic_base_url=required["ANTHROPIC_BASE_URL"],  # type: ignore[arg-type]
        anthropic_model=required["ANTHROPIC_MODEL"],  # type: ignore[arg-type]
        api_key=api_key,  # type: ignore[arg-type]
        bocha_api_key=bocha_key,
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        upload_dir=upload_dir,
        otel_exporter_otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
        otel_exporter_otlp_headers=os.getenv("OTEL_EXPORTER_OTLP_HEADERS", ""),
    )
    # Mirror values into the environment for the SDK to consume.
    settings.apply_to_env()

    # Inform operators whether telemetry is active.
    if settings.otel_exporter_otlp_endpoint:
        print(
            f"[config] OpenTelemetry enabled: endpoint={settings.otel_exporter_otlp_endpoint}",
            file=sys.stderr,
        )
    else:
        print("[config] OpenTelemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)", file=sys.stderr)

    return settings


# Eagerly validated singleton used across the backend.
settings = validate_settings()
