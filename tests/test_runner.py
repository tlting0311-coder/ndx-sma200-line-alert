from __future__ import annotations

from datetime import date, timedelta

from ndx_signal.models import BUY, PushResult, PriceBar
from ndx_signal.runner import run_check
from tests.fakes import FakeLineClient, FakeStore


def buy_bars(symbol):
    start = date(2026, 1, 1)
    return [
        PriceBar(date=start + timedelta(days=index), close=close)
        for index, close in enumerate([10.0, 10.0, 10.0, 12.0])
    ]


def test_dry_run_reports_signal_and_subscriber_count_without_push():
    store = FakeStore(["U1", "U2"])
    line_client = FakeLineClient()

    summary = run_check("^NDX", 3, buy_bars, store, line_client, send=False)

    assert summary.signal == BUY
    assert summary.subscriber_count == 2
    assert summary.sent_count == 0
    assert line_client.push_calls == []
    assert store.latest_signal_key is None


def test_duplicate_signal_skips_all_subscribers():
    store = FakeStore(["U1", "U2"])
    store.latest_signal_key = "2026-01-04:BUY"
    line_client = FakeLineClient()

    summary = run_check("^NDX", 3, buy_bars, store, line_client, send=True)

    assert summary.duplicate is True
    assert summary.skipped_count == 2
    assert summary.sent_count == 0
    assert line_client.push_calls == []


def test_push_continues_when_one_user_has_non_retryable_failure():
    store = FakeStore(["U1", "U2", "U3"])
    line_client = FakeLineClient(
        {"U2": PushResult(ok=False, retryable=False, status_code=400, error="invalid user")}
    )

    summary = run_check("^NDX", 3, buy_bars, store, line_client, send=True)

    assert summary.sent_count == 2
    assert summary.failed_count == 1
    assert summary.retryable_failed_count == 0
    assert store.latest_signal_key == "2026-01-04:BUY"
    assert store.deliveries[("2026-01-04:BUY", "U1")] == "success"
    assert store.deliveries[("2026-01-04:BUY", "U2")] == "failed"
    assert store.deliveries[("2026-01-04:BUY", "U3")] == "success"


def test_retryable_failure_does_not_mark_signal_as_latest():
    store = FakeStore(["U1"])
    line_client = FakeLineClient(
        {"U1": PushResult(ok=False, retryable=True, status_code=500, error="server error")}
    )

    summary = run_check("^NDX", 3, buy_bars, store, line_client, send=True)

    assert summary.retryable_failed_count == 1
    assert store.latest_signal_key is None
