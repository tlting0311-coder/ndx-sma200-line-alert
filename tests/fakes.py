from __future__ import annotations

from typing import Dict, Iterable, Optional, Set, Tuple

from ndx_signal.models import PushResult, SignalResult, Subscriber


class FakeStore:
    def __init__(self, subscribers: Optional[Iterable[str]] = None):
        self.active: Set[str] = set(subscribers or [])
        self.latest_signal_key: Optional[str] = None
        self.deliveries: Dict[Tuple[str, str], str] = {}

    def subscribe_user(self, user_id: str, display_name: Optional[str] = None) -> None:
        self.active.add(user_id)

    def unsubscribe_user(self, user_id: str) -> None:
        self.active.discard(user_id)

    def is_subscribed(self, user_id: str) -> bool:
        return user_id in self.active

    def list_active_subscribers(self) -> Iterable[Subscriber]:
        return [Subscriber(user_id=user_id) for user_id in sorted(self.active)]

    def get_latest_signal_key(self) -> Optional[str]:
        return self.latest_signal_key

    def set_latest_signal(self, signal_key: str, result: SignalResult) -> None:
        self.latest_signal_key = signal_key

    def was_delivery_successful(self, signal_key: str, user_id: str) -> bool:
        return self.deliveries.get((signal_key, user_id)) == "success"

    def mark_delivery(
        self,
        signal_key: str,
        user_id: str,
        status: str,
        status_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        self.deliveries[(signal_key, user_id)] = status


class FakeLineClient:
    def __init__(self, push_results: Optional[Dict[str, PushResult]] = None):
        self.push_results = push_results or {}
        self.push_calls = []
        self.reply_calls = []

    def push_text(self, user_id: str, text: str) -> PushResult:
        self.push_calls.append((user_id, text))
        return self.push_results.get(user_id, PushResult(ok=True, retryable=False, status_code=200))

    def reply_text(self, reply_token: str, text: str) -> PushResult:
        self.reply_calls.append((reply_token, text))
        return PushResult(ok=True, retryable=False, status_code=200)
