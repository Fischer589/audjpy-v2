"""Continuation engine: corrective failure detection + probability scoring."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.models.candle import Candle
from src.strategy.trend_bias import TrendBias
from src.strategy.corrective_structure import CorrectivePattern
from src.config import BotSettings

logger = logging.getLogger(__name__)

PIP = 0.01


@dataclass
class FailureSignal:
    detected: bool
    failure_type: str
    clarity: float
    trigger_price: float
    trigger_candle_idx: int


@dataclass
class ContinuationSetup:
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    continuation_prob: float
    volatility_regime: str
    atr_current: float
    notes: list[str]


_NO_FAILURE = FailureSignal(
    detected=False, failure_type="none", clarity=0.0,
    trigger_price=0.0, trigger_candle_idx=0,
)


def _atr_avg(candles: list[Candle], period: int) -> float:
    if len(candles) < 2:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        prev = candles[i - 1].close
        trs.append(max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - prev),
            abs(candles[i].low - prev),
        ))
    n = min(period, len(trs))
    return sum(trs[-n:]) / n


def detect_failure(
    candles_5m: list[Candle],
    pattern: CorrectivePattern,
    trend_direction: str,
    settings: BotSettings,
) -> FailureSignal:
    if not candles_5m or pattern.pattern_type == "none":
        return _NO_FAILURE

    latest = candles_5m[-1]
    prev = candles_5m[-2] if len(candles_5m) >= 2 else None
    prev2 = candles_5m[-3] if len(candles_5m) >= 3 else None

    ub = pattern.upper_bound
    lb = pattern.lower_bound

    if trend_direction == "bullish":
        if latest.close > ub and latest.is_bullish:
            atr = _atr_avg(candles_5m[-20:], 14)
            excess = latest.close - ub
            clarity = min(1.0, excess / (atr * 0.5)) if atr > 0 else 0.5
            if latest.body_ratio > 0.55:
                clarity = min(1.0, clarity + 0.15)
            return FailureSignal(
                detected=True, failure_type="boundary_break",
                clarity=round(clarity, 3),
                trigger_price=latest.close, trigger_candle_idx=-1,
            )

        if prev and prev.close > ub and latest.low < ub and latest.close > ub:
            clarity = 0.55 + (latest.body_ratio * 0.20)
            if latest.lower_wick_ratio > 0.35:
                clarity += 0.10
            return FailureSignal(
                detected=True, failure_type="failed_reentry",
                clarity=round(min(1.0, clarity), 3),
                trigger_price=latest.close, trigger_candle_idx=-1,
            )

        if prev and prev2 and prev.close > ub and prev2.close > ub and latest.close > ub:
            return FailureSignal(
                detected=True, failure_type="acceptance",
                clarity=0.70,
                trigger_price=latest.close, trigger_candle_idx=-1,
            )

        if prev and prev.close < lb and latest.close > lb:
            clarity = 0.50 + (latest.body_ratio * 0.20)
            return FailureSignal(
                detected=True, failure_type="reclaim",
                clarity=round(min(1.0, clarity), 3),
                trigger_price=latest.close, trigger_candle_idx=-1,
            )

    else:
        if latest.close < lb and latest.is_bearish:
            atr = _atr_avg(candles_5m[-20:], 14)
            excess = lb - latest.close
            clarity = min(1.0, excess / (atr * 0.5)) if atr > 0 else 0.5
            if latest.body_ratio > 0.55:
                clarity = min(1.0, clarity + 0.15)
            return FailureSignal(
                detected=True, failure_type="boundary_break",
                clarity=round(clarity, 3),
                trigger_price=latest.close, trigger_candle_idx=-1,
            )

        if prev and prev.close < lb and latest.high > lb and latest.close < lb:
            clarity = 0.55 + (latest.body_ratio * 0.20)
            if latest.upper_wick_ratio > 0.35:
                clarity += 0.10
            return FailureSignal(
                detected=True, failure_type="failed_reentry",
                clarity=round(min(1.0, clarity), 3),
                trigger_price=latest.close, trigger_candle_idx=-1,
            )

        if prev and prev2 and prev.close < lb and prev2.close < lb and latest.close < lb:
            return FailureSignal(
                detected=True, failure_type="acceptance",
                clarity=0.70,
                trigger_price=latest.close, trigger_candle_idx=-1,
            )

        if prev and prev.close > ub and latest.close < ub:
            clarity = 0.50 + (latest.body_ratio * 0.20)
            return FailureSignal(
                detected=True, failure_type="reclaim",
                clarity=round(min(1.0, clarity), 3),
                trigger_price=latest.close, trigger_candle_idx=-1,
            )

    return _NO_FAILURE


def _classify_volatility(
    candles_5m: list[Candle],
    candles_1h: list[Candle],
    settings: BotSettings,
) -> tuple[str, float]:
    baseline_atr = _atr_avg(candles_5m[-settings.atr_baseline_period:], settings.atr_baseline_period)
    recent_atr = _atr_avg(candles_5m[-10:], 10)

    if baseline_atr < 1e-9:
        return "unknown", recent_atr

    ratio = recent_atr / baseline_atr

    if ratio < settings.atr_compression_threshold:
        recent = candles_5m[-20:]
        overlap = sum(
            1 for i in range(len(recent) - 1) if recent[i].overlaps_with(recent[i + 1])
        ) / max(1, len(recent) - 1)

        bodies = [c.body for c in recent]
        half = len(bodies) // 2
        body_ratio_chg = (sum(bodies[half:]) / max(1, len(bodies) - half)) / (sum(bodies[:half]) / max(1, half))

        if overlap > 0.50 and body_ratio_chg < 0.85:
            return "compressed_structured", recent_atr
        else:
            return "compressed_chop", recent_atr

    if ratio > settings.atr_chaotic_threshold:
        return "chaotic", recent_atr

    return "normal", recent_atr


def evaluate_continuation(
    candles_5m: list[Candle],
    candles_1h: list[Candle],
    trend: TrendBias,
    pattern: CorrectivePattern,
    failure: FailureSignal,
    settings: BotSettings,
) -> ContinuationSetup:
    direction = "long" if trend.direction == "bullish" else "short"
    vol_regime, atr_now = _classify_volatility(candles_5m, candles_1h, settings)

    notes: list[str] = []

    trend_score = trend.confidence
    correction_score = pattern.quality * (0.7 + 0.3 * pattern.exhaustion_score)
    failure_score = failure.clarity if failure.detected else 0.0

    vol_scores = {
        "compressed_structured": 0.85,
        "normal": 0.65,
        "compressed_chop": 0.35,
        "expanding": 0.50,
        "chaotic": 0.20,
        "unknown": 0.40,
    }
    vol_score = vol_scores.get(vol_regime, 0.40)

    mp_mod = {"accelerating": 1.08, "steady": 1.0, "decelerating": 0.90, "unknown": 0.95}
    momentum_mod = mp_mod.get(trend.momentum_phase, 1.0)

    prob = (
        trend_score * 0.30
        + correction_score * 0.25
        + failure_score * 0.25
        + vol_score * 0.20
    ) * momentum_mod

    prob = round(min(1.0, max(0.0, prob)), 3)

    entry = failure.trigger_price
    atr = atr_now if atr_now > 1e-9 else (0.05 * len(candles_5m) / 1000)

    sl_distance = atr * settings.stop_loss_atr_multiplier
    tp_distance = sl_distance * settings.take_profit_rr

    if direction == "long":
        stop_loss = round(entry - sl_distance, 5)
        take_profit = round(entry + tp_distance, 5)
        corr_low = min(c.low for c in candles_5m[-pattern.candle_count:]) if pattern.candle_count > 0 else stop_loss
        if corr_low < stop_loss:
            stop_loss = round(corr_low - atr * 0.3, 5)
            notes.append("sl_adjusted_to_corrective_low")
    else:
        stop_loss = round(entry + sl_distance, 5)
        take_profit = round(entry - tp_distance, 5)
        corr_high = max(c.high for c in candles_5m[-pattern.candle_count:]) if pattern.candle_count > 0 else stop_loss
        if corr_high > stop_loss:
            stop_loss = round(corr_high + atr * 0.3, 5)
            notes.append("sl_adjusted_to_corrective_high")

    actual_risk = abs(entry - stop_loss)
    actual_reward = abs(entry - take_profit)
    rr = round(actual_reward / actual_risk, 2) if actual_risk > 1e-9 else 0.0

    return ContinuationSetup(
        direction=direction,
        entry_price=round(entry, 5),
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=rr,
        continuation_prob=prob,
        volatility_regime=vol_regime,
        atr_current=round(atr, 5),
        notes=notes,
    )
