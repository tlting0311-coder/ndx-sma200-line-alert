from __future__ import annotations

import base64
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from ndx_signal.app import create_app
from ndx_signal.config import Settings
from tests.fakes import FakeLineClient, FakeStore


SECRET = "test-secret"


def signed_headers(body: bytes):
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return {"X-Line-Signature": base64.b64encode(digest).decode("utf-8")}


def post_event(client, event):
    body = json.dumps({"events": [event]}, ensure_ascii=False).encode("utf-8")
    return client.post("/line/webhook", content=body, headers=signed_headers(body))


def message_event(text, user_id="U1", reply_token="reply-token"):
    return {
        "type": "message",
        "replyToken": reply_token,
        "source": {"type": "user", "userId": user_id},
        "message": {"type": "text", "text": text},
    }


def make_client():
    store = FakeStore()
    line_client = FakeLineClient()
    app = create_app(
        settings=Settings(
            line_channel_secret=SECRET,
            line_channel_access_token="token",
        ),
        store=store,
        line_client=line_client,
    )
    return TestClient(app), store, line_client


def test_subscribe_message_adds_user_and_replies():
    client, store, line_client = make_client()

    response = post_event(client, message_event("訂閱"))

    assert response.status_code == 200
    assert store.is_subscribed("U1") is True
    assert line_client.reply_calls == [("reply-token", "已訂閱 Nasdaq 100 SMA200 訊號通知。")]


def test_cancel_message_removes_user_and_replies():
    client, store, line_client = make_client()
    store.subscribe_user("U1")

    response = post_event(client, message_event("取消"))

    assert response.status_code == 200
    assert store.is_subscribed("U1") is False
    assert line_client.reply_calls == [("reply-token", "已取消 Nasdaq 100 SMA200 訊號通知。")]


def test_status_message_reports_subscription_state():
    client, store, line_client = make_client()
    store.subscribe_user("U1")

    response = post_event(client, message_event("狀態"))

    assert response.status_code == 200
    assert line_client.reply_calls == [
        ("reply-token", "目前狀態：已訂閱 Nasdaq 100 SMA200 訊號通知。")
    ]


def test_unknown_text_replies_with_available_commands():
    client, store, line_client = make_client()

    response = post_event(client, message_event("hello"))

    assert response.status_code == 200
    assert store.is_subscribed("U1") is False
    assert line_client.reply_calls == [("reply-token", "請輸入「訂閱」、「取消」或「狀態」。")]


def test_invalid_signature_is_rejected():
    client, store, line_client = make_client()
    body = json.dumps({"events": [message_event("訂閱")]}, ensure_ascii=False).encode("utf-8")

    response = client.post("/line/webhook", content=body, headers={"X-Line-Signature": "bad"})

    assert response.status_code == 403
    assert store.is_subscribed("U1") is False
    assert line_client.reply_calls == []
