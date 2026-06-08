from __future__ import annotations

from typing import Iterable, List, Tuple

from ndx_signal.models import BUY, NONE, SELL, PriceBar, SignalResult


class InsufficientDataError(ValueError):
    """Raised when there is not enough price history to evaluate a crossover."""


def evaluate_sma_cross(
    bars: Iterable[PriceBar],
    window: int,
    symbol: str,
) -> SignalResult:
    ordered_bars = sorted(list(bars), key=lambda bar: bar.date)
    if len(ordered_bars) < window + 1:
        raise InsufficientDataError(
            f"Need at least {window + 1} bars to compare current and previous SMA"
        )

    rows = _bars_with_sma(ordered_bars, window)
    if len(rows) < 2:
        raise InsufficientDataError("Need at least two bars with SMA values")

    previous_bar, previous_sma = rows[-2]
    current_bar, current_sma = rows[-1]

    previous_delta = previous_bar.close - previous_sma
    current_delta = current_bar.close - current_sma

    signal = NONE
    if previous_delta <= 0 and current_delta > 0:
        signal = BUY
    elif previous_delta >= 0 and current_delta < 0:
        signal = SELL

    return SignalResult(
        symbol=symbol,
        signal=signal,
        signal_date=current_bar.date,
        close=current_bar.close,
        sma=current_sma,
        previous_date=previous_bar.date,
        previous_close=previous_bar.close,
        previous_sma=previous_sma,
    )


def _bars_with_sma(bars: List[PriceBar], window: int) -> List[Tuple[PriceBar, float]]:
    rows: List[Tuple[PriceBar, float]] = []
    rolling_sum = 0.0

    for index, bar in enumerate(bars):
        rolling_sum += bar.close
        if index >= window:
            rolling_sum -= bars[index - window].close
        if index >= window - 1:
            rows.append((bar, rolling_sum / window))

    return rows


def format_signal_message(result: SignalResult) -> str:
    action = "買入訊號" if result.signal == BUY else "賣出訊號"
    return (
        f"【Nasdaq 100 SMA200 {action}】\n"
        f"標的：{result.symbol}\n"
        f"日期：{result.signal_date.isoformat()}\n"
        f"收盤價：{result.close:,.2f}\n"
        f"SMA200：{result.sma:,.2f}\n"
        f"前一交易日：{result.previous_date.isoformat()} "
        f"收盤 {result.previous_close:,.2f} / SMA {result.previous_sma:,.2f}\n"
        "訊號提醒，非投資建議。"
    )
