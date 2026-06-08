from __future__ import annotations

from datetime import date
from typing import List

from ndx_signal.models import PriceBar


class MarketDataError(RuntimeError):
    """Raised when price history cannot be loaded or parsed."""


def load_yfinance_bars(symbol: str) -> List[PriceBar]:
    try:
        import pandas as pd
        import yfinance as yf
    except ImportError as exc:
        raise MarketDataError("yfinance and pandas are required for market data") from exc

    frame = yf.download(
        symbol,
        period="2y",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if frame.empty:
        raise MarketDataError(f"No price data returned for {symbol}")

    try:
        close_series = frame["Close"]
    except KeyError as exc:
        raise MarketDataError("Downloaded data does not include a Close column") from exc

    if isinstance(close_series, pd.DataFrame):
        if symbol in close_series.columns:
            close_series = close_series[symbol]
        else:
            close_series = close_series.iloc[:, 0]

    close_series = close_series.dropna()
    if close_series.empty:
        raise MarketDataError(f"No non-null close prices returned for {symbol}")

    bars: List[PriceBar] = []
    for index_value, close in close_series.items():
        if hasattr(index_value, "date"):
            bar_date = index_value.date()
        elif isinstance(index_value, date):
            bar_date = index_value
        else:
            raise MarketDataError(f"Unexpected date index value: {index_value!r}")
        bars.append(PriceBar(date=bar_date, close=float(close)))

    return bars
