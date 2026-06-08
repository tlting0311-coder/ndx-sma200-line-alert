from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Optional

import requests

from ndx_signal.models import PushResult


LINE_API_BASE = "https://api.line.me/v2/bot"


class LineClient:
    def __init__(self, channel_access_token: str, timeout_seconds: float = 10.0):
        self.channel_access_token = channel_access_token
        self.timeout_seconds = timeout_seconds

    def push_text(self, user_id: str, text: str) -> PushResult:
        return self._send_message(
            endpoint=f"{LINE_API_BASE}/message/push",
            payload={"to": user_id, "messages": [{"type": "text", "text": text}]},
        )

    def reply_text(self, reply_token: str, text: str) -> PushResult:
        return self._send_message(
            endpoint=f"{LINE_API_BASE}/message/reply",
            payload={"replyToken": reply_token, "messages": [{"type": "text", "text": text}]},
        )

    def _send_message(self, endpoint: str, payload: dict) -> PushResult:
        headers = {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            return PushResult(ok=False, retryable=True, error=str(exc))

        if 200 <= response.status_code < 300:
            return PushResult(ok=True, retryable=False, status_code=response.status_code)

        retryable = response.status_code == 429 or response.status_code >= 500
        return PushResult(
            ok=False,
            retryable=retryable,
            status_code=response.status_code,
            error=response.text[:500],
        )


def verify_line_signature(channel_secret: str, body: bytes, signature: Optional[str]) -> bool:
    if not signature:
        return False
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)
