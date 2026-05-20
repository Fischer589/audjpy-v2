"""AUDJPY V2 — Entry point.

Usage:
    python main.py [--config config/settings.yaml] [--local config/settings.local.yaml]

Reads settings -> connects to IBKR -> starts live monitor.
Press Ctrl+C to stop cleanly.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.config import load_settings
from src.data.candle_feed import IbkrCandleFeed
from src.risk.risk_manager import RiskManager
from src.runtime.ibkr_connection import IbkrConnection
from src.runtime.live_monitor import LiveMonitor


def _setup_logging(log_file: str, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s %(levelname)-5s %(name)s  %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)


def main() -> None:
    parser = argparse.ArgumentParser(description="AUDJPY V2 continuation bot")
    parser.add_argument("--config", default="config/settings.yaml", help="Main config path")
    parser.add_argument("--local", default=None, help="Local override config path")
    args = parser.parse_args()

    settings = load_settings(config_path=args.config, local_path=args.local)

    _setup_logging(settings.log_file_path, settings.verbose_logging)

    logger = logging.getLogger("main")
    logger.info("=" * 60)
    logger.info("AUDJPY V2  mode=%s  symbol=%s", settings.execution_mode, settings.symbol)
    logger.info("=" * 60)

    if settings.live_trading:
        logger.warning("!!! LIVE TRADING ENABLED — real money at risk !!!")

    for d in [settings.journal_directory, settings.snapshot_directory]:
        Path(d).mkdir(parents=True, exist_ok=True)

    connection = IbkrConnection(settings)
    connection.connect()

    feed = IbkrCandleFeed(settings, connection)
    risk = RiskManager(settings)
    monitor = LiveMonitor(settings, feed, risk)

    try:
        monitor.run()
    finally:
        connection.disconnect()


if __name__ == "__main__":
    main()
