from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, Optional

from fastapi import FastAPI, HTTPException, Request

from ndx_signal.config import Settings
from ndx_signal.line_client import LineClient, verify_line_signature
from ndx_signal.market import load_yfinance_bars
from ndx_signal.models import PriceBar
from ndx_signal.signals import (
    InsufficientDataError,
    evaluate_sma_status,
    format_sma_status_message,
)
from ndx_signal.store import AlertStore, FirestoreStore

logger = logging.getLogger(__name__)

MarketLoader = Callable[[str], Iterable[PriceBar]]


def create_app(
    settings: Optional[Settings] = None,
    store: Optional[AlertStore] = None,
    line_client: Optional[LineClient] = None,
    market_loader: MarketLoader = load_yfinance_bars,
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
            _handle_line_event(
                event,
                get_store(),
                get_line_client(),
                get_settings(),
                market_loader,
            )

        return {"ok": True}

    return app


def _handle_line_event(
    event: dict,
    store: AlertStore,
    line_client: LineClient,
    settings: Settings,
    market_loader: MarketLoader,
) -> None:
    source = event.get("source") or {}
    user_id = source.get("userId")
    reply_token = event.get("replyToken")

    if not user_id:
        logger.info("Ignoring LINE event without userId: %s", event.get("type"))
        return

    event_type = event.get("type")
    if event_type == "follow":
        _reply_if_possible(line_client, reply_token, _format_help_message())
        return

    if event_type != "message":
        return

    message = event.get("message") or {}
    if message.get("type") != "text":
        _reply_if_possible(line_client, reply_token, _format_help_message())
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
    elif _is_help_query(text):
        _reply_if_possible(line_client, reply_token, _format_help_message())
    elif _is_market_status_query(text):
        try:
            status = evaluate_sma_status(
                market_loader(settings.symbol),
                window=settings.sma_window,
                symbol=settings.symbol,
            )
            reply = format_sma_status_message(status)
        except Exception as exc:
            if not isinstance(exc, InsufficientDataError):
                logger.exception("Failed to load SMA status")
            else:
                logger.warning("Insufficient data for SMA status: %s", exc)
            reply = "暫時查不到 Nasdaq 100 SMA200 行情資料，請稍後再試。"
        _reply_if_possible(line_client, reply_token, reply)
    else:
        _reply_if_possible(line_client, reply_token, _format_help_message())


def _format_help_message() -> str:
    return (
        "【可用功能】\n"
        "訂閱：接收 Nasdaq 100 穿越 SMA200 的買入/賣出通知\n"
        "取消：停止接收自動通知\n"
        "狀態：查詢目前是否已訂閱\n"
        "NDX：查最新收盤價、SMA200、距離均線幾點與百分比\n"
        "功能：再次顯示這份選單\n"
        "訊號提醒，非投資建議。"
    )


def _is_help_query(text: str) -> bool:
    normalized = text.strip().lower().replace(" ", "")
    keywords = (
        "help",
        "?",
        "？",
        "功能",
        "幫助",
        "指令",
        "使用說明",
        "怎麼用",
        "可以查詢什麼",
        "可查詢什麼",
        "查詢什麼",
    )
    return any(keyword in normalized for keyword in keywords)


def _is_market_status_query(text: str) -> bool:
    normalized = text.strip().lower().replace(" ", "")
    keywords = (
        "ndx",
        "nasdaq",
        "納斯達克",
        "那斯達克",
        "查詢",
        "現在多少",
        "200日",
        "200日均線",
        "sma200",
        "均線",
    )
    return any(keyword in normalized for keyword in keywords)


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
