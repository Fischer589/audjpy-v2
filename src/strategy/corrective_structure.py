"""Corrective structure detection on 5M candles."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.models.candle import Candle
from src.config import BotSettings

logger = logging.getLogger(__name__)


@dataclass
class CorrectivePattern:
    pattern_type: str
    upper_bound: float
    lower_bound: float
    upper_slope: float
    lower_slope: float
    compression_score: float
    atr_ratio: float
    overlap_score: float
    exhaustion_score: float
    candle_count: int
    quality: float


_NONE = CorrectivePattern(
    pattern_type="none",
    upper_bound=0.0, lower_bound=0.0,
    upper_slope=0.0, lower_slope=0.0,
    compression_score=0.0, atr_ratio=1.0,
    overlap_score=0.0, exhaustion_score=0.0,
    candle_count=0, quality=0.0,
)


def _linreg(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return 0.0, sy / n
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _atr_avg(candles: list[Candle], period: int) -> float:
    if len(candles) < 2:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        prev = candles[i - 1].close
        tr = max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - prev),
            abs(candles[i].low - prev),
        )
        trs.append(tr)
    n = min(period, len(trs))
    return sum(trs[-n:]) / n


def _overlap_score(candles: list[Candle]) -> float:
    if len(candles) < 2:
        return 0.0
    overlaps = sum(1 for i in range(len(candles) - 1) if candles[i].overlaps_with(candles[i + 1]))
    return overlaps / (len(candles) - 1)


def _velocity_decay(candles: list[Candle]) -> float:
    if len(candles) < 6:
        return 0.0
    half = len(candles) // 2
    first_vel = sum(c.body for c in candles[:half]) / half
    second_vel = sum(c.body for c in candles[half:]) / max(1, len(candles) - half)
    if first_vel < 1e-9:
        return 0.5
    decay = 1.0 - min(1.0, second_vel / first_vel)
    return max(0.0, decay)


def _find_correction_start(
    candles: list[Candle],
    trend_direction: str,
    min_bars: int,
    max_bars: int,
) -> Optional[int]:
    search = candles[-max_bars:] if len(candles) > max_bars else candles
    offset = len(candles) - len(search)

    if trend_direction == "bullish":
        best_i = None
        best_val = -1e18
        for i in range(len(search) - min_bars):
            if search[i].high > best_val:
                best_val = search[i].high
                best_i = i
        if best_i is None:
            return None
        post = search[best_i:]
        if len(post) < min_bars:
            return None
        if post[-1].close >= best_val * 0.9999:
            return None
        return offset + best_i
    else:
        best_i = None
        best_val = 1e18
        for i in range(len(search) - min_bars):
            if search[i].low < best_val:
                best_val = search[i].low
                best_i = i
        if best_i is None:
            return None
        post = search[best_i:]
        if len(post) < min_bars:
            return None
        if post[-1].close <= best_val * 1.0001:
            return None
        return offset + best_i


def _classify_pattern(
    upper_slope: float,
    lower_slope: float,
    compression_ratio: float,
    atr_ratio: float,
    overlap: float,
    trend_dir: str,
    n_bars: int,
) -> str:
    if overlap > 0.65 and atr_ratio < 0.65:
        return "compression"

    if trend_dir == "bullish":
        both_declining = upper_slope < -1e-6 and lower_slope < -1e-6
        converging = upper_slope > lower_slope
    else:
        both_rising = upper_slope > 1e-6 and lower_slope > 1e-6
        converging = lower_slope > upper_slope

    if trend_dir == "bullish":
        if both_declining:
            if converging and compression_ratio < 0.80:
                return "wedge"
            return "descending_channel"
    else:
        if both_rising:
            if converging and compression_ratio < 0.80:
                return "wedge"
            return "ascending_channel"

    if n_bars <= 20 and atr_ratio > 0.80:
        return "tight_pullback"

    return "drift"


_PATTERN_QUALITY = {
    "descending_channel": 0.85,
    "ascending_channel": 0.85,
    "wedge": 0.90,
    "compression": 0.80,
    "tight_pullback": 0.65,
    "drift": 0.45,
    "none": 0.0,
}


def detect_correction(
    candles_5m: list[Candle],
    trend_direction: str,
    settings: BotSettings,
) -> CorrectivePattern:
    if trend_direction == "neutral":
        return _NONE

    start_idx = _find_correction_start(
        candles_5m,
        trend_direction,
        settings.min_correction_bars,
        settings.max_correction_bars,
    )

    if start_idx is None:
        return _NONE

    corr = candles_5m[start_idx:]
    n = len(corr)

    if n < settings.min_correction_bars:
        return _NONE

    xs = list(range(n))
    highs = [c.high for c in corr]
    lows = [c.low for c in corr]

    upper_slope, upper_int = _linreg(xs, highs)
    lower_slope, lower_int = _linreg(xs, lows)

    upper_at_latest = upper_slope * (n - 1) + upper_int
    lower_at_latest = lower_slope * (n - 1) + lower_int

    initial_width = upper_int - lower_int
    current_width = upper_at_latest - lower_at_latest
    if initial_width > 1e-9:
        compression_score = max(0.0, 1.0 - current_width / initial_width)
    else:
        compression_score = 0.0

    baseline_window = candles_5m[-(settings.atr_baseline_period + n):-n] if n < len(candles_5m) else candles_5m
    baseline_atr = _atr_avg(baseline_window, settings.atr_baseline_period)
    recent_atr = _atr_avg(corr[-min(10, n):], 10)
    atr_ratio = recent_atr / baseline_atr if baseline_atr > 1e-9 else 1.0

    overlap = _overlap_score(corr)
    vel_decay = _velocity_decay(corr)

    pattern_type = _classify_pattern(
        upper_slope, lower_slope,
        1.0 - compression_score,
        atr_ratio, overlap,
        trend_direction, n,
    )

    atr_contraction = max(0.0, 1.0 - atr_ratio)
    exhaustion = (
        compression_score * 0.30
        + atr_contraction * 0.35
        + overlap * 0.20
        + vel_decay * 0.15
    )
    exhaustion = min(1.0, max(0.0, exhaustion))

    base_q = _PATTERN_QUALITY.get(pattern_type, 0.5)
    quality = base_q * (0.6 + 0.4 * exhaustion)

    logger.debug(
        "[correction] type=%s n=%d atr_ratio=%.2f compression=%.2f overlap=%.2f exhaustion=%.2f",
        pattern_type, n, atr_ratio, compression_score, overlap, exhaustion,
    )

    return CorrectivePattern(
        pattern_type=pattern_type,
        upper_bound=round(upper_at_latest, 5),
        lower_bound=round(lower_at_latest, 5),
        upper_slope=round(upper_slope, 7),
        lower_slope=round(lower_slope, 7),
        compression_score=round(compression_score, 3),
        atr_ratio=round(atr_ratio, 3),
        overlap_score=round(overlap, 3),
        exhaustion_score=round(exhaustion, 3),
        candle_count=n,
        quality=round(quality, 3),
    )
