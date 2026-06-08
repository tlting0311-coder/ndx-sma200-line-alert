from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request

from ndx_signal.config import Settings
from ndx_signal.line_client import LineClient, verify_line_signature
from ndx_signal.store import AlertStore, FirestoreStore

logger = logging.getLogger(__name__)


def create_app(
    settings: Optional[Settings] = None,
    store: Optional[AlertStore] = None,
    line_client: Optional[LineClient] = None,
) -> FastAPI:
    app = FastAPI(title="NDX SMA200 LINE Alert")
    state: Dict[str, Any] = {
        "settings": settings,
        "store": store,
        "line_client": line_client,
    }

    def get_settings() -> Settings:
        if state["settings"] is None:
            state["settings"] = Settings.from_env()
        return state["settings"]

    def get_store() -> AlertStore:
        if state["store"] is None:
            current_settings = get_settings()
            state["store"] = FirestoreStore(project=current_settings.google_cloud_project)
        return state["store"]

    def get_line_client() -> LineClient:
        if state["line_client"] is None:
            current_settings = get_settings()
            state["line_client"] = LineClient(current_settings.require_line_access_token())
        return state["line_client"]

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.post("/line/webhook")
    async def line_webhook(request: Request) -> dict:
        current_settings = get_settings()
        body = await request.body()
        signature = request.headers.get("X-Line-Signature")

        if not verify_line_signature(
            current_settings.require_line_channel_secret(),
            body,
            signature,
        ):
            raise HTTPException(status_code=403, detail="Invalid LINE signature")

        payload = await request.json()
        for event in payload.get("events", []):
            _handle_line_event(event, get_store(), get_line_client())

        return {"ok": True}

    return app


def _handle_line_event(event: dict, store: AlertStore, line_client: LineClient) -> None:
    source = event.get("source") or {}
    user_id = source.get("userId")
    reply_token = event.get("replyToken")

    if not user_id:
        logger.info("Ignoring LINE event without userId: %s", event.get("type"))
        return

    event_type = event.get("type")
    if event_type == "follow":
        _reply_if_possible(
            line_client,
            reply_token,
            "歡迎使用 Nasdaq 100 SMA200 訊號通知。請輸入「訂閱」開始接收通知。",
        )
        return

    if event_type != "message":
        return

    message = event.get("message") or {}
    if message.get("type") != "text":
        _reply_if_possible(line_client, reply_token, "請輸入「訂閱」、「取消」或「狀態」。")
        return

    text = str(message.get("text", "")).strip()
    if text == "訂閱":
        store.subscribe_user(user_id)
        _reply_if_possible(line_client, reply_token, "已訂閱 Nasdaq 100 SMA200 訊號通知。")
    elif text == "取消":
        store.unsubscribe_user(user_id)
        _reply_if_possible(line_client, reply_token, "已取消 Nasdaq 100 SMA200 訊號通知。")
    elif text == "狀態":
        if store.is_subscribed(user_id):
            reply = "目前狀態：已訂閱 Nasdaq 100 SMA200 訊號通知。"
        else:
            reply = "目前狀態：尚未訂閱。請輸入「訂閱」開始接收通知。"
        _reply_if_possible(line_client, reply_token, reply)
    else:
        _reply_if_possible(line_client, reply_token, "請輸入「訂閱」、「取消」或「狀態」。")


def _reply_if_possible(line_client: LineClient, reply_token: Optional[str], text: str) -> None:
    if not reply_token:
        return
    result = line_client.reply_text(reply_token, text)
    if not result.ok:
        logger.warning(
            "LINE reply failed status=%s retryable=%s error=%s",
            result.status_code,
            result.retryable,
            result.error,
        )


app = create_app()
