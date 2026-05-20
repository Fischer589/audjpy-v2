"""HTF trend analysis.

Measures directional bias from 1H + 4H candles using:
  - EMA alignment (20/50)
  - Swing structure (HH/HL vs LH/LL sequence)
  - Impulse quality (body ratio on trend-direction candles)
  - Momentum phase (ATR trend: accelerating / steady / decelerating)
  - 1H/4H directional alignment
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.models.candle import Candle
from src.config import BotSettings

logger = logging.getLogger(__name__)


@dataclass
class TrendBias:
    direction: str
    strength: float
    impulse_quality: float
    momentum_phase: str
    swing_4h: str
    swing_1h: str
    ema_aligned_4h: bool
    ema_aligned_1h: bool
    htf_aligned: bool
    confidence: float


def _ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    result = [sum(values[:period]) / period]
    for v in values[period:]:
        result.append(v * k + result[-1] * (1.0 - k))
    return result


def _atr_series(candles: list[Candle]) -> list[float]:
    result = []
    for i in range(1, len(candles)):
        prev = candles[i - 1].close
        tr = max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - prev),
            abs(candles[i].low - prev),
        )
        result.append(tr)
    return result


def _atr_avg(candles: list[Candle], period: int = 14) -> float:
    trs = _atr_series(candles)
    if not trs:
        return 0.0
    n = min(period, len(trs))
    return sum(trs[-n:]) / n


def _swing_highs(candles: list[Candle], n: int = 3) -> list[tuple[int, float]]:
    result = []
    for i in range(n, len(candles) - n):
        if all(candles[i].high >= candles[j].high for j in range(i - n, i + n + 1) if j != i):
            result.append((i, candles[i].high))
    return result


def _swing_lows(candles: list[Candle], n: int = 3) -> list[tuple[int, float]]:
    result = []
    for i in range(n, len(candles) - n):
        if all(candles[i].low <= candles[j].low for j in range(i - n, i + n + 1) if j != i):
            result.append((i, candles[i].low))
    return result


def _classify_swings(highs: list[tuple], lows: list[tuple]) -> str:
    if len(highs) < 2 or len(lows) < 2:
        return "neutral"
    hh = highs[-1][1] > highs[-2][1]
    hl = lows[-1][1] > lows[-2][1]
    lh = highs[-1][1] < highs[-2][1]
    ll = lows[-1][1] < lows[-2][1]
    if hh and hl:
        return "bullish"
    if lh and ll:
        return "bearish"
    return "neutral"


def _impulse_quality(candles: list[Candle], direction: str) -> float:
    if direction == "bullish":
        subset = [c for c in candles if c.is_bullish and c.range > 0]
    elif direction == "bearish":
        subset = [c for c in candles if c.is_bearish and c.range > 0]
    else:
        return 0.0
    if not subset:
        return 0.0
    return sum(c.body_ratio for c in subset) / len(subset)


def _momentum_phase(candles: list[Candle], period: int = 14) -> str:
    if len(candles) < period * 2 + 2:
        return "unknown"
    recent = _atr_avg(candles[-(period + 1):], period)
    prior = _atr_avg(candles[-(period * 2 + 1):-(period)], period)
    if prior < 1e-9:
        return "unknown"
    ratio = recent / prior
    if ratio > 1.15:
        return "accelerating"
    if ratio < 0.85:
        return "decelerating"
    return "steady"


def analyze_htf_trend(
    candles_1h: list[Candle],
    candles_4h: list[Candle],
    settings: BotSettings,
) -> TrendBias:
    n = settings.swing_pivot_bars

    closes_4h = [c.close for c in candles_4h]
    ema20_4h = _ema(closes_4h, 20)
    ema50_4h = _ema(closes_4h, 50)
    ema_4h_ok = len(ema20_4h) >= 1 and len(ema50_4h) >= 1

    if ema_4h_ok:
        price_4h = closes_4h[-1]
        bullish_4h = ema20_4h[-1] > ema50_4h[-1] and price_4h > ema20_4h[-1]
        bearish_4h = ema20_4h[-1] < ema50_4h[-1] and price_4h < ema20_4h[-1]
    else:
        bullish_4h = bearish_4h = False

    highs_4h = _swing_highs(candles_4h, n)
    lows_4h = _swing_lows(candles_4h, n)
    swing_4h = _classify_swings(highs_4h, lows_4h)

    closes_1h = [c.close for c in candles_1h]
    ema20_1h = _ema(closes_1h, 20)
    ema50_1h = _ema(closes_1h, 50)
    ema_1h_ok = len(ema20_1h) >= 1 and len(ema50_1h) >= 1

    if ema_1h_ok:
        price_1h = closes_1h[-1]
        bullish_1h = ema20_1h[-1] > ema50_1h[-1] and price_1h > ema20_1h[-1]
        bearish_1h = ema20_1h[-1] < ema50_1h[-1] and price_1h < ema20_1h[-1]
    else:
        bullish_1h = bearish_1h = False

    highs_1h = _swing_highs(candles_1h, n)
    lows_1h = _swing_lows(candles_1h, n)
    swing_1h = _classify_swings(highs_1h, lows_1h)

    bull_votes = sum([
        int(bullish_4h),
        int(swing_4h == "bullish"),
        int(bullish_1h),
        int(swing_1h == "bullish"),
    ])
    bear_votes = sum([
        int(bearish_4h),
        int(swing_4h == "bearish"),
        int(bearish_1h),
        int(swing_1h == "bearish"),
    ])

    if bull_votes >= 3:
        direction = "bullish"
    elif bear_votes >= 3:
        direction = "bearish"
    elif bull_votes == 2 and bullish_4h and swing_4h == "bullish":
        direction = "bullish"
    elif bear_votes == 2 and bearish_4h and swing_4h == "bearish":
        direction = "bearish"
    else:
        direction = "neutral"

    if direction == "bullish":
        strength_components = [
            1.0 if bullish_4h else 0.0,
            1.0 if swing_4h == "bullish" else 0.5 if swing_4h == "neutral" else 0.0,
            1.0 if bullish_1h else 0.5,
            1.0 if swing_1h == "bullish" else 0.5 if swing_1h == "neutral" else 0.0,
        ]
    elif direction == "bearish":
        strength_components = [
            1.0 if bearish_4h else 0.0,
            1.0 if swing_4h == "bearish" else 0.5 if swing_4h == "neutral" else 0.0,
            1.0 if bearish_1h else 0.5,
            1.0 if swing_1h == "bearish" else 0.5 if swing_1h == "neutral" else 0.0,
        ]
    else:
        strength_components = [0.0]

    strength = sum(strength_components) / len(strength_components)

    iq = _impulse_quality(candles_4h[-20:], direction) if direction != "neutral" else 0.0
    mp = _momentum_phase(candles_1h)
    htf_aligned = (bullish_4h and bullish_1h) or (bearish_4h and bearish_1h)
    alignment_factor = 1.0 if htf_aligned else (0.7 if not settings.require_1h_4h_alignment else 0.4)
    mp_factor = {"accelerating": 1.10, "steady": 1.0, "decelerating": 0.85, "unknown": 0.90}[mp]

    confidence = min(1.0, strength * 0.55 + iq * 0.30 + 0.15)
    confidence = min(1.0, confidence * alignment_factor * mp_factor)

    if direction == "neutral":
        confidence = 0.0
        strength = 0.0
        iq = 0.0

    return TrendBias(
        direction=direction,
        strength=round(strength, 3),
        impulse_quality=round(iq, 3),
        momentum_phase=mp,
        swing_4h=swing_4h,
        swing_1h=swing_1h,
        ema_aligned_4h=bullish_4h or bearish_4h,
        ema_aligned_1h=bullish_1h or bearish_1h,
        htf_aligned=htf_aligned,
        confidence=round(confidence, 3),
    )
