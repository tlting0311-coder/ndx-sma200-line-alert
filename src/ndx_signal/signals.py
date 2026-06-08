from __future__ import annotations

from typing import Iterable, List, Tuple

from ndx_signal.models import BUY, NONE, SELL, PriceBar, SignalResult, SmaStatus


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


def evaluate_sma_status(
    bars: Iterable[PriceBar],
    window: int,
    symbol: str,
) -> SmaStatus:
    ordered_bars = sorted(list(bars), key=lambda bar: bar.date)
    if len(ordered_bars) < window:
        raise InsufficientDataError(f"Need at least {window} bars to calculate SMA")

    current_bar, current_sma = _bars_with_sma(ordered_bars, window)[-1]
    return SmaStatus(
        symbol=symbol,
        window=window,
        date=current_bar.date,
        close=current_bar.close,
        sma=current_sma,
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
    if result.signal == BUY:
        title = "Nasdaq 100 站回 200日均線"
        playbook = "賣出 QQQ，all in TQQQ"
        tone = "趨勢轉強，切換進攻配置。"
    elif result.signal == SELL:
        title = "Nasdaq 100 跌破 200日均線"
        playbook = "賣出 TQQQ，all in QQQ"
        tone = "趨勢轉弱，切換防守配置。"
    else:
        title = "無新訊號"
        playbook = "維持原策略"
        tone = "先坐穩，等下一個明確方向。"

    return (
        f"【{title}】\n"
        f"策略動作：{playbook}\n"
        f"{tone}\n"
        f"標的：{result.symbol}\n"
        f"日期：{result.signal_date.isoformat()}\n"
        f"收盤價：{result.close:,.2f}\n"
        f"SMA200：{result.sma:,.2f}\n"
        f"前一交易日：{result.previous_date.isoformat()} "
        f"收盤 {result.previous_close:,.2f} / SMA {result.previous_sma:,.2f}\n"
        "依你的策略設定提醒，非投資建議。"
    )


def format_sma_status_message(status: SmaStatus) -> str:
    signed_distance = f"{status.distance:+,.2f}"
    signed_percent = f"{status.distance_percent:+.2f}%"
    return (
        f"【Nasdaq 100 SMA{status.window} 查詢】\n"
        f"標的：{status.symbol}\n"
        f"日期：{status.date.isoformat()}\n"
        f"最新收盤價：{status.close:,.2f}\n"
        f"SMA{status.window}：{status.sma:,.2f}\n"
        f"距離均線：{status.position_label} {abs(status.distance):,.2f} 點 "
        f"({signed_distance} / {signed_percent})\n"
        "資料為最新可取得行情，非投資建議。"
    )
