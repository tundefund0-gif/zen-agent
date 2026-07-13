"""Application configuration — environment variables with .env support and validation."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _load_dotenv():
    """Load .env file if present (lightweight, no dependency)."""
    env_path = Path(__file__).parent / ".env"
    if env_path.is_file():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if len(val) > 1 and val[0] == val[-1] and val[0] in ('"', "'"):
                    val = val[1:-1]
                if key not in os.environ:
                    os.environ[key] = val


_load_dotenv()


def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _get_env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").lower().strip()
    if not val:
        return default
    return val in ("1", "true", "yes", "on")


def validate_api_key(key: str, name: str) -> Optional[str]:
    if not key or len(key) < 8:
        return None
    return key


def validate_url(url: str) -> str:
    url = url.rstrip("/")
    if not re.match(r"^https?://", url):
        raise ValueError(f"Invalid URL: {url}")
    return url


@dataclass
class Config:
    # LLM / OpenCode
    opencode_api_key: str = field(default_factory=lambda: _get_env("OPENGATE_API_KEY", ""))
    opencode_base_url: str = field(
        default_factory=lambda: validate_url(_get_env("OPENGATE_BASE_URL", "https://opencode.ai/zen/v1"))
    )
    opencode_model: str = field(default_factory=lambda: _get_env("OPENGATE_MODEL", "deepseek-v4-flash-free"))
    opencode_max_tokens: int = field(default_factory=lambda: _get_env_int("OPENGATE_MAX_TOKENS", 131000))
    opencode_timeout: int = field(default_factory=lambda: _get_env_int("OPENGATE_TIMEOUT", 180))

    # Composio
    composio_api_key: str = field(default_factory=lambda: _get_env("COMPOSIO_API_KEY", ""))
    composio_base_url: str = field(
        default_factory=lambda: validate_url(_get_env("COMPOSIO_BASE_URL", "https://backend.composio.dev"))
    )
    composio_timeout: int = field(default_factory=lambda: _get_env_int("COMPOSIO_TIMEOUT", 60))

    # Server
    host: str = field(default_factory=lambda: _get_env("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _get_env_int("PORT", 8000))
    log_level: str = field(default_factory=lambda: _get_env("LOG_LEVEL", "info"))
    cors_origins: str = field(default_factory=lambda: _get_env("CORS_ORIGINS", "*"))
    rate_limit: int = field(default_factory=lambda: _get_env_int("RATE_LIMIT", 60))

    # Agent
    max_tool_rounds: int = field(default_factory=lambda: _get_env_int("MAX_TOOL_ROUNDS", 10000))
    max_history: int = field(default_factory=lambda: _get_env_int("MAX_HISTORY", 100))
    enable_sandbox: bool = field(default_factory=lambda: _get_env_bool("ENABLE_SANDBOX", True))

    def __post_init__(self):
        self.opencode_base_url = self.opencode_base_url.rstrip("/")
        self.composio_base_url = self.composio_base_url.rstrip("/")

    @property
    def has_opencode_key(self) -> bool:
        return bool(self.opencode_api_key and len(self.opencode_api_key) >= 8)

    @property
    def has_composio_key(self) -> bool:
        return bool(self.composio_api_key and len(self.composio_api_key) >= 8)

    @property
    def is_configured(self) -> bool:
        return self.has_opencode_key and self.has_composio_key


config = Config()
