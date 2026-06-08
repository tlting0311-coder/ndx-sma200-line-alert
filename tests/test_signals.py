from __future__ import annotations

from datetime import date, timedelta

import pytest

from ndx_signal.models import BUY, NONE, SELL, PriceBar
from ndx_signal.signals import (
    InsufficientDataError,
    evaluate_sma_cross,
    evaluate_sma_status,
    format_sma_status_message,
)


def bars(closes):
    start = date(2026, 1, 1)
    return [
        PriceBar(date=start + timedelta(days=index), close=float(close))
        for index, close in enumerate(closes)
    ]


def test_buy_signal_when_close_crosses_above_sma():
    result = evaluate_sma_cross(bars([10, 10, 10, 12]), window=3, symbol="^NDX")

    assert result.signal == BUY
    assert result.signal_key == "2026-01-04:BUY"


def test_sell_signal_when_close_crosses_below_sma():
    result = evaluate_sma_cross(bars([10, 10, 10, 8]), window=3, symbol="^NDX")

    assert result.signal == SELL
    assert result.signal_key == "2026-01-04:SELL"


def test_none_when_price_does_not_cross():
    result = evaluate_sma_cross(bars([10, 10, 10, 10]), window=3, symbol="^NDX")

    assert result.signal == NONE
    assert result.signal_key is None


def test_insufficient_data_requires_current_and_previous_sma():
    with pytest.raises(InsufficientDataError):
        evaluate_sma_cross(bars([10, 11, 12]), window=3, symbol="^NDX")


def test_sma_status_reports_latest_close_distance_and_percent():
    status = evaluate_sma_status(bars([10, 10, 16]), window=3, symbol="^NDX")

    assert status.date == date(2026, 1, 3)
    assert status.close == 16
    assert status.sma == 12
    assert status.distance == 4
    assert status.distance_percent == pytest.approx(33.333333)
    assert status.position_label == "高於"


def test_format_sma_status_message_contains_distance():
    status = evaluate_sma_status(bars([10, 10, 16]), window=3, symbol="^NDX")

    message = format_sma_status_message(status)

    assert "最新收盤價：16.00" in message
    assert "SMA3：12.00" in message
    assert "距離均線：高於 4.00 點 (+4.00 / +33.33%)" in message
