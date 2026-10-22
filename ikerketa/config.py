"""Centralized configuration using pydantic-settings.

All configuration is loaded from environment variables (via .env file)
and validated at startup. Missing required values cause immediate failure
with clear error messages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── API Tokens ──────────────────────────────────────────────────────
    eppo_api_token: str = Field(
        default="",
        description="EPPO Global Database API token",
    )
    dg_sante_api_key: str = Field(
        default="",
        description="DG SANTE Developer Portal API key",
    )
    cabi_api_key: str = Field(
        default="",
        description="CABI CPC subscription API key (optional)",
    )

    # ── SPARQL Endpoints ────────────────────────────────────────────────
    agrovoc_sparql_endpoint: str = Field(
        default="https://agrovoc.fao.org/sparql",
        description="AGROVOC SPARQL endpoint URL",
    )

    # ── Directories ─────────────────────────────────────────────────────
    data_raw_dir: Path = Field(default=_PROJECT_ROOT / "data" / "raw")
    data_processed_dir: Path = Field(default=_PROJECT_ROOT / "data" / "processed")
    data_reports_dir: Path = Field(default=_PROJECT_ROOT / "data" / "reports")

    # ── Logging ─────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")

    # ── Connector behavior ──────────────────────────────────────────────
    http_timeout_seconds: int = Field(default=30)
    http_max_retries: int = Field(default=3)
    http_retry_backoff_base: float = Field(default=2.0)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            msg = f"Invalid log level '{v}'. Must be one of {valid}"
            raise ValueError(msg)
        return upper

    def ensure_dirs(self) -> None:
        """Create data directories if they don't exist."""
        for d in (self.data_raw_dir, self.data_processed_dir, self.data_reports_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_sources_config(path: Path | None = None) -> dict[str, Any]:
    """Load the sources.yaml registry.

    Returns the parsed YAML as a dict. Raises FileNotFoundError
    if the config file is missing.
    """
    if path is None:
        path = _PROJECT_ROOT / "configs" / "sources.yaml"
    if not path.exists():
        msg = f"Sources config not found at {path}"
        raise FileNotFoundError(msg)
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Singleton — import once, use everywhere
settings = Settings()
