"""Synthetic candle generators for tests."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.models.candle import Candle

_BASE_PRICE = 90.00
_BASE_TS = datetime(2026, 1, 20, 8, 0, tzinfo=timezone.utc)
_5M = timedelta(minutes=5)
_1H = timedelta(hours=1)
_4H = timedelta(hours=4)


def _ts(i: int, interval: timedelta) -> datetime:
    return _BASE_TS + interval * i


def make_bullish_trend_5m(
    n: int = 60,
    step: float = 0.015,
    noise: float = 0.005,
) -> list[Candle]:
    candles = []
    price = _BASE_PRICE
    for i in range(n):
        o = price + ((-1) ** i) * noise
        c = price + step + noise * 0.5
        h = max(o, c) + noise
        l = min(o, c) - noise * 0.3
        candles.append(Candle(_ts(i, _5M), o, h, l, c))
        price = c
    return candles


def make_bearish_trend_5m(
    n: int = 60,
    step: float = 0.015,
    noise: float = 0.005,
) -> list[Candle]:
    candles = []
    price = _BASE_PRICE
    for i in range(n):
        o = price - ((-1) ** i) * noise
        c = price - step - noise * 0.5
        h = max(o, c) + noise * 0.3
        l = min(o, c) - noise
        candles.append(Candle(_ts(i, _5M), o, h, l, c))
        price = c
    return candles


def make_htf_bullish(n: int = 50, interval: timedelta = _1H) -> list[Candle]:
    candles = []
    price = _BASE_PRICE
    for i in range(n):
        body = 0.04 + 0.01 * (i % 3)
        o = price
        c = price + body
        h = c + 0.015
        l = o - 0.005
        candles.append(Candle(_ts(i, interval), o, h, l, c))
        price = c + 0.005
    return candles


def make_htf_bearish(n: int = 50, interval: timedelta = _1H) -> list[Candle]:
    candles = []
    price = _BASE_PRICE
    for i in range(n):
        body = 0.04 + 0.01 * (i % 3)
        o = price
        c = price - body
        h = o + 0.005
        l = c - 0.015
        candles.append(Candle(_ts(i, interval), o, h, l, c))
        price = c - 0.005
    return candles


def make_htf_mixed(n: int = 50, interval: timedelta = _1H) -> list[Candle]:
    candles = []
    price = _BASE_PRICE
    for i in range(n):
        direction = 1 if i % 4 < 2 else -1
        body = 0.02
        o = price
        c = price + direction * body
        h = max(o, c) + 0.01
        l = min(o, c) - 0.01
        candles.append(Candle(_ts(i, interval), o, h, l, c))
        price = c
    return candles


def make_descending_channel(
    n: int = 25,
    start_price: float = 90.10,
    step: float = -0.012,
    width: float = 0.04,
    offset: int = 0,
) -> list[Candle]:
    candles = []
    for i in range(n):
        mid = start_price + step * i
        wave = math.sin(i * math.pi * 2 / 5) * width * 0.5
        o = mid + wave
        c = mid + step * 0.7 + wave * 0.3
        h = max(o, c) + width * 0.3
        l = min(o, c) - width * 0.3
        ts = _BASE_TS + _5M * (offset + i)
        candles.append(Candle(ts, round(o, 5), round(h, 5), round(l, 5), round(c, 5)))
    return candles


def make_compression(
    n: int = 20,
    start_price: float = 90.00,
    tightening: float = 0.002,
    offset: int = 0,
) -> list[Candle]:
    candles = []
    price = start_price
    for i in range(n):
        half_range = max(tightening, 0.025 - tightening * i)
        o = price
        c = price + ((-1) ** i) * half_range * 0.3
        h = max(o, c) + half_range * 0.5
        l = min(o, c) - half_range * 0.5
        ts = _BASE_TS + _5M * (offset + i)
        candles.append(Candle(ts, round(o, 5), round(h, 5), round(l, 5), round(c, 5)))
        price = c
    return candles


def make_breakout_candle(
    prev_candle: Candle,
    direction: str,
    strength: float = 0.05,
) -> Candle:
    ts = prev_candle.timestamp + _5M
    if direction == "up":
        o = prev_candle.close
        c = o + strength
        h = c + strength * 0.2
        l = o - strength * 0.05
    else:
        o = prev_candle.close
        c = o - strength
        l = c - strength * 0.2
        h = o + strength * 0.05
    return Candle(ts, round(o, 5), round(h, 5), round(l, 5), round(c, 5))


def make_duplicate_sequence(base: list[Candle], n_dupes: int = 3) -> list[Candle]:
    last = base[-1]
    dupes = []
    for i in range(1, n_dupes + 1):
        dupes.append(Candle(last.timestamp, last.open, last.high, last.low, last.close, last.volume))
    return base + dupes
