from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from typing import Optional, Sequence

from ndx_signal.config import Settings
from ndx_signal.line_client import LineClient
from ndx_signal.market import load_yfinance_bars
from ndx_signal.runner import run_check
from ndx_signal.store import FirestoreStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ndx-signal")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Check Nasdaq 100 SMA200 signal")
    mode = check_parser.add_mutually_exclusive_group()
    mode.add_argument("--send", action="store_true", help="Send LINE alerts on new signals")
    mode.add_argument("--dry-run", action="store_true", help="Check without sending LINE alerts")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)

    if args.command == "check":
        return _run_check_command(send=bool(args.send))

    raise RuntimeError(f"Unsupported command: {args.command}")


def _run_check_command(send: bool) -> int:
    settings = Settings.from_env()
    store = FirestoreStore(project=settings.google_cloud_project)
    line_client = None
    if send:
        line_client = LineClient(settings.require_line_access_token())

    summary = run_check(
        symbol=settings.symbol,
        sma_window=settings.sma_window,
        market_loader=load_yfinance_bars,
        store=store,
        line_client=line_client,
        send=send,
    )

    print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True))
    if summary.retryable_failed_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
