from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


class ConfigError(RuntimeError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True)
class Settings:
    symbol: str = "^NDX"
    sma_window: int = 200
    timezone: str = "Asia/Taipei"
    google_cloud_project: Optional[str] = None
    line_channel_access_token: Optional[str] = None
    line_channel_secret: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Settings":
        sma_window_raw = os.getenv("SMA_WINDOW", "200")
        try:
            sma_window = int(sma_window_raw)
        except ValueError as exc:
            raise ConfigError("SMA_WINDOW must be an integer") from exc

        if sma_window <= 1:
            raise ConfigError("SMA_WINDOW must be greater than 1")

        return cls(
            symbol=os.getenv("SYMBOL", "^NDX"),
            sma_window=sma_window,
            timezone=os.getenv("TIMEZONE", "Asia/Taipei"),
            google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
            line_channel_secret=os.getenv("LINE_CHANNEL_SECRET"),
        )

    def require_line_access_token(self) -> str:
        if not self.line_channel_access_token:
            raise ConfigError("LINE_CHANNEL_ACCESS_TOKEN is required")
        return self.line_channel_access_token

    def require_line_channel_secret(self) -> str:
        if not self.line_channel_secret:
            raise ConfigError("LINE_CHANNEL_SECRET is required")
        return self.line_channel_secret
