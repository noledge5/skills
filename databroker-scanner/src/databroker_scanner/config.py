"""Application configuration, loaded from config.yaml and validated."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Validated runtime settings. Unknown keys are rejected to catch typos."""

    model_config = {"extra": "forbid"}

    # Browser
    headless: bool = False
    slowmo_ms: int = 0
    proxy: str | None = None
    browser: str = "chromium"

    # Concurrency & politeness
    parallel: int = Field(default=2, ge=1, le=16)
    per_domain_delay_s: float = Field(default=4.0, ge=0)
    timeout_ms: int = Field(default=30000, ge=1000)
    retry: int = Field(default=3, ge=0, le=10)

    # Output
    screenshot: bool = True
    save_html: bool = True
    save_json: bool = True
    save_csv: bool = True

    # Storage
    db_path: str = "results/scanner.db"
    output_dir: str = "reports"
    screenshot_dir: str = "screenshots"

    # Compliance
    respect_robots: bool = True
    user_agent: str = (
        "DataBrokerScanner/0.1 "
        "(+https://github.com/noledge5/databroker-scanner; personal-privacy-audit)"
    )

    @classmethod
    def load(cls, path: str | Path | None = None) -> Settings:
        """Load settings from ``path`` (defaults to ./config.yaml if present)."""
        if path is None:
            candidate = Path("config.yaml")
            if not candidate.exists():
                return cls()  # sensible defaults; no config file required
            path = candidate
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)
