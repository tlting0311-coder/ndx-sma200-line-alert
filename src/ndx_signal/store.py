from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional, Protocol

from ndx_signal.models import SignalResult, Subscriber


class AlertStore(Protocol):
    def subscribe_user(self, user_id: str, display_name: Optional[str] = None) -> None:
        ...

    def unsubscribe_user(self, user_id: str) -> None:
        ...

    def is_subscribed(self, user_id: str) -> bool:
        ...

    def list_active_subscribers(self) -> Iterable[Subscriber]:
        ...

    def get_latest_signal_key(self) -> Optional[str]:
        ...

    def set_latest_signal(self, signal_key: str, result: SignalResult) -> None:
        ...

    def was_delivery_successful(self, signal_key: str, user_id: str) -> bool:
        ...

    def mark_delivery(
        self,
        signal_key: str,
        user_id: str,
        status: str,
        status_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        ...


class FirestoreStore:
    def __init__(self, project: Optional[str] = None):
        from google.cloud import firestore

        self._firestore = firestore
        self.client = firestore.Client(project=project)

    def subscribe_user(self, user_id: str, display_name: Optional[str] = None) -> None:
        data = {
            "user_id": user_id,
            "active": True,
            "updated_at": self._firestore.SERVER_TIMESTAMP,
        }
        if display_name:
            data["display_name"] = display_name
        doc_ref = self.client.collection("subscriptions").document(user_id)
        snapshot = doc_ref.get()
        if not snapshot.exists:
            data["created_at"] = self._firestore.SERVER_TIMESTAMP
        doc_ref.set(data, merge=True)

    def unsubscribe_user(self, user_id: str) -> None:
        self.client.collection("subscriptions").document(user_id).set(
            {
                "user_id": user_id,
                "active": False,
                "updated_at": self._firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def is_subscribed(self, user_id: str) -> bool:
        snapshot = self.client.collection("subscriptions").document(user_id).get()
        if not snapshot.exists:
            return False
        return bool(snapshot.to_dict().get("active"))

    def list_active_subscribers(self) -> Iterable[Subscriber]:
        query = self.client.collection("subscriptions").where("active", "==", True)
        for snapshot in query.stream():
            data = snapshot.to_dict()
            user_id = data.get("user_id") or snapshot.id
            yield Subscriber(user_id=user_id, display_name=data.get("display_name"))

    def get_latest_signal_key(self) -> Optional[str]:
        snapshot = self.client.collection("app_state").document("latest_signal").get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict().get("signal_key")

    def set_latest_signal(self, signal_key: str, result: SignalResult) -> None:
        self.client.collection("app_state").document("latest_signal").set(
            {
                "signal_key": signal_key,
                "signal_type": result.signal,
                "signal_date": result.signal_date.isoformat(),
                "close": result.close,
                "sma": result.sma,
                "updated_at": self._firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def was_delivery_successful(self, signal_key: str, user_id: str) -> bool:
        snapshot = (
            self.client.collection("signals")
            .document(signal_key)
            .collection("deliveries")
            .document(user_id)
            .get()
        )
        if not snapshot.exists:
            return False
        return snapshot.to_dict().get("status") == "success"

    def mark_delivery(
        self,
        signal_key: str,
        user_id: str,
        status: str,
        status_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        self.client.collection("signals").document(signal_key).set(
            {"signal_key": signal_key, "updated_at": self._firestore.SERVER_TIMESTAMP},
            merge=True,
        )
        self.client.collection("signals").document(signal_key).collection(
            "deliveries"
        ).document(user_id).set(
            {
                "user_id": user_id,
                "status": status,
                "status_code": status_code,
                "error": error,
                "updated_at": self._firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
