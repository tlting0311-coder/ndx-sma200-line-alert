from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import date, timedelta

from fastapi.testclient import TestClient

from ndx_signal.app import create_app
from ndx_signal.config import Settings
from ndx_signal.models import PriceBar
from tests.fakes import FakeLineClient, FakeStore


SECRET = "test-secret"
HELP_MESSAGE = (
    "【可用功能】\n"
    "訂閱：接收 Nasdaq 100 穿越 SMA200 的買入/賣出通知\n"
    "取消：停止接收自動通知\n"
    "狀態：查詢目前是否已訂閱\n"
    "NDX：查最新收盤價、SMA200、距離均線幾點與百分比\n"
    "功能：再次顯示這份選單\n"
    "訊號提醒，非投資建議。"
)


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


def follow_event(user_id="U1", reply_token="reply-token"):
    return {
        "type": "follow",
        "replyToken": reply_token,
        "source": {"type": "user", "userId": user_id},
    }


def fake_market_loader(symbol):
    start = date(2026, 1, 1)
    return [
        PriceBar(date=start + timedelta(days=index), close=close)
        for index, close in enumerate([10.0, 10.0, 16.0])
    ]


def make_client(market_loader=fake_market_loader):
    store = FakeStore()
    line_client = FakeLineClient()
    app = create_app(
        settings=Settings(
            symbol="^NDX",
            sma_window=3,
            line_channel_secret=SECRET,
            line_channel_access_token="token",
        ),
        store=store,
        line_client=line_client,
        market_loader=market_loader,
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
    assert line_client.reply_calls == [("reply-token", HELP_MESSAGE)]


def test_follow_event_replies_with_help_menu():
    client, store, line_client = make_client()

    response = post_event(client, follow_event())

    assert response.status_code == 200
    assert line_client.reply_calls == [("reply-token", HELP_MESSAGE)]


def test_help_query_replies_with_help_menu_instead_of_market_query():
    client, store, line_client = make_client()

    response = post_event(client, message_event("可以查詢什麼？"))

    assert response.status_code == 200
    assert line_client.reply_calls == [("reply-token", HELP_MESSAGE)]


def test_ndx_query_replies_with_latest_close_and_sma_distance():
    client, store, line_client = make_client()

    response = post_event(client, message_event("NDX現在多少"))

    assert response.status_code == 200
    assert line_client.reply_calls == [
        (
            "reply-token",
            "【Nasdaq 100 SMA3 查詢】\n"
            "標的：^NDX\n"
            "日期：2026-01-03\n"
            "最新收盤價：16.00\n"
            "SMA3：12.00\n"
            "距離均線：高於 4.00 點 (+4.00 / +33.33%)\n"
            "資料為最新可取得行情，非投資建議。",
        )
    ]


def test_ndx_query_handles_market_data_failure():
    def failing_loader(symbol):
        raise RuntimeError("market unavailable")

    client, store, line_client = make_client(market_loader=failing_loader)

    response = post_event(client, message_event("查詢"))

    assert response.status_code == 200
    assert line_client.reply_calls == [("reply-token", "暫時查不到 Nasdaq 100 SMA200 行情資料，請稍後再試。")]


def test_invalid_signature_is_rejected():
    client, store, line_client = make_client()
    body = json.dumps({"events": [message_event("訂閱")]}, ensure_ascii=False).encode("utf-8")

    response = client.post("/line/webhook", content=body, headers={"X-Line-Signature": "bad"})

    assert response.status_code == 403
    assert store.is_subscribed("U1") is False
    assert line_client.reply_calls == []
