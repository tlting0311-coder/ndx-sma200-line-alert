from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


BUY = "BUY"
SELL = "SELL"
NONE = "NONE"


@dataclass(frozen=True)
class PriceBar:
    date: date
    close: float


@dataclass(frozen=True)
class SignalResult:
    symbol: str
    signal: str
    signal_date: date
    close: float
    sma: float
    previous_date: date
    previous_close: float
    previous_sma: float

    @property
    def signal_key(self) -> Optional[str]:
        if self.signal == NONE:
            return None
        return f"{self.signal_date.isoformat()}:{self.signal}"


@dataclass(frozen=True)
class Subscriber:
    user_id: str
    display_name: Optional[str] = None


@dataclass(frozen=True)
class PushResult:
    ok: bool
    retryable: bool
    status_code: Optional[int] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class CheckRunSummary:
    symbol: str
    signal: str
    signal_key: Optional[str]
    signal_date: str
    close: float
    sma: float
    subscriber_count: int
    sent_count: int
    skipped_count: int
    failed_count: int
    retryable_failed_count: int
    duplicate: bool
    send_enabled: bool
