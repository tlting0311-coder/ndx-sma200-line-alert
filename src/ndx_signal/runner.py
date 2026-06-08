from __future__ import annotations

import logging
from typing import Callable, Iterable, Optional

from ndx_signal.models import NONE, CheckRunSummary, PriceBar, PushResult
from ndx_signal.signals import evaluate_sma_cross, format_signal_message
from ndx_signal.store import AlertStore

logger = logging.getLogger(__name__)


MarketLoader = Callable[[str], Iterable[PriceBar]]


class PushClientProtocol:
    def push_text(self, user_id: str, text: str) -> PushResult:
        raise NotImplementedError


def run_check(
    symbol: str,
    sma_window: int,
    market_loader: MarketLoader,
    store: AlertStore,
    line_client: Optional[PushClientProtocol],
    send: bool,
) -> CheckRunSummary:
    result = evaluate_sma_cross(market_loader(symbol), window=sma_window, symbol=symbol)
    subscribers = list(store.list_active_subscribers())

    duplicate = False
    sent_count = 0
    skipped_count = 0
    failed_count = 0
    retryable_failed_count = 0
    signal_key = result.signal_key

    if result.signal == NONE or signal_key is None:
        return CheckRunSummary(
            symbol=symbol,
            signal=result.signal,
            signal_key=None,
            signal_date=result.signal_date.isoformat(),
            close=result.close,
            sma=result.sma,
            subscriber_count=len(subscribers),
            sent_count=0,
            skipped_count=0,
            failed_count=0,
            retryable_failed_count=0,
            duplicate=False,
            send_enabled=send,
        )

    latest_signal_key = store.get_latest_signal_key()
    if latest_signal_key == signal_key:
        duplicate = True
        skipped_count = len(subscribers)
    elif send:
        if line_client is None:
            raise RuntimeError("line_client is required when send=True")

        message = format_signal_message(result)
        for subscriber in subscribers:
            if store.was_delivery_successful(signal_key, subscriber.user_id):
                skipped_count += 1
                continue

            push_result = line_client.push_text(subscriber.user_id, message)
            if push_result.ok:
                sent_count += 1
                store.mark_delivery(signal_key, subscriber.user_id, "success")
                continue

            failed_count += 1
            if push_result.retryable:
                retryable_failed_count += 1
                logger.warning(
                    "Retryable LINE push failure user_id=%s status=%s error=%s",
                    subscriber.user_id,
                    push_result.status_code,
                    push_result.error,
                )
            else:
                store.mark_delivery(
                    signal_key,
                    subscriber.user_id,
                    "failed",
                    status_code=push_result.status_code,
                    error=push_result.error,
                )
                logger.warning(
                    "Non-retryable LINE push failure user_id=%s status=%s error=%s",
                    subscriber.user_id,
                    push_result.status_code,
                    push_result.error,
                )

        if retryable_failed_count == 0:
            store.set_latest_signal(signal_key, result)

    return CheckRunSummary(
        symbol=symbol,
        signal=result.signal,
        signal_key=signal_key,
        signal_date=result.signal_date.isoformat(),
        close=result.close,
        sma=result.sma,
        subscriber_count=len(subscribers),
        sent_count=sent_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        retryable_failed_count=retryable_failed_count,
        duplicate=duplicate,
        send_enabled=send,
    )
