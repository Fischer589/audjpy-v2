"""Tests for continuation_engine.py."""
from __future__ import annotations
import pytest
from datetime import timedelta

from src.strategy.continuation_engine import detect_failure, evaluate_continuation
from src.strategy.corrective_structure import CorrectivePattern
from src.strategy.trend_bias import TrendBias
from tests.fixtures.candles import (
    make_bullish_trend_5m,
    make_descending_channel,
    make_breakout_candle,
)
from tests.fixtures.candles import _BASE_TS, _5M


def _make_trend_bias(direction="bullish", confidence=0.65) -> TrendBias:
    return TrendBias(
        direction=direction,
        strength=0.75,
        impulse_quality=0.65,
        momentum_phase="steady",
        swing_4h=direction,
        swing_1h=direction,
        ema_aligned_4h=True,
        ema_aligned_1h=True,
        htf_aligned=True,
        confidence=confidence,
    )


def _make_pattern(ub=90.08, lb=90.02) -> CorrectivePattern:
    return CorrectivePattern(
        pattern_type="descending_channel",
        upper_bound=ub,
        lower_bound=lb,
        upper_slope=-0.001,
        lower_slope=-0.001,
        compression_score=0.40,
        atr_ratio=0.65,
        overlap_score=0.55,
        exhaustion_score=0.45,
        candle_count=20,
        quality=0.72,
    )


class TestBoundaryBreakLong:
    def _build(self, ub=90.08):
        from src.models.candle import Candle
        trend = make_bullish_trend_5m(30, step=0.02)
        corr = make_descending_channel(20, start_price=trend[-1].close, offset=30)
        prev = corr[-1]
        breakout = Candle(
            prev.timestamp + _5M,
            prev.close,
            ub + 0.06,
            prev.close - 0.005,
            ub + 0.04,
        )
        return trend + corr + [breakout], _make_pattern(ub=ub, lb=ub - 0.06)

    def test_boundary_break_detected(self, settings):
        candles, pattern = self._build()
        failure = detect_failure(candles, pattern, "bullish", settings)
        assert failure.detected
        assert failure.failure_type == "boundary_break"

    def test_clarity_in_range(self, settings):
        candles, pattern = self._build()
        failure = detect_failure(candles, pattern, "bullish", settings)
        assert 0.0 <= failure.clarity <= 1.0

    def test_trigger_price_is_last_close(self, settings):
        candles, pattern = self._build()
        failure = detect_failure(candles, pattern, "bullish", settings)
        assert failure.trigger_price == candles[-1].close


class TestNoFailure:
    def test_inside_correction_no_failure(self, settings):
        trend = make_bullish_trend_5m(30, step=0.02)
        corr = make_descending_channel(20, start_price=trend[-1].close, offset=30)
        candles = trend + corr
        last_close = candles[-1].close
        pattern = _make_pattern(ub=last_close + 0.10, lb=last_close - 0.10)
        failure = detect_failure(candles, pattern, "bullish", settings)
        assert not failure.detected
        assert failure.failure_type == "none"

    def test_no_candles_returns_no_failure(self, settings):
        failure = detect_failure([], _make_pattern(), "bullish", settings)
        assert not failure.detected

    def test_none_pattern_returns_no_failure(self, settings):
        from src.strategy.corrective_structure import _NONE
        candles = make_bullish_trend_5m(30)
        failure = detect_failure(candles, _NONE, "bullish", settings)
        assert not failure.detected


class TestEvaluateContinuation:
    def test_returns_setup_with_long_direction(self, settings):
        trend = make_bullish_trend_5m(50, step=0.02)
        corr = make_descending_channel(20, start_price=trend[-1].close, offset=50)
        all_candles = trend + corr

        from src.strategy.continuation_engine import FailureSignal
        failure = FailureSignal(
            detected=True,
            failure_type="boundary_break",
            clarity=0.75,
            trigger_price=all_candles[-1].close,
            trigger_candle_idx=-1,
        )
        pattern = _make_pattern(ub=all_candles[-1].close - 0.01, lb=all_candles[-1].close - 0.07)
        trend_bias = _make_trend_bias("bullish", 0.70)
        c1h = make_bullish_trend_5m(48, step=0.015)

        setup = evaluate_continuation(all_candles, c1h, trend_bias, pattern, failure, settings)

        assert setup.direction == "long"
        assert setup.entry_price > 0
        assert setup.stop_loss < setup.entry_price
        assert setup.take_profit > setup.entry_price
        assert setup.risk_reward > 0
        assert 0.0 <= setup.continuation_prob <= 1.0

    def test_stop_loss_below_entry_for_long(self, settings):
        trend = make_bullish_trend_5m(50, step=0.02)
        corr = make_descending_channel(20, start_price=trend[-1].close, offset=50)
        all_candles = trend + corr

        from src.strategy.continuation_engine import FailureSignal
        failure = FailureSignal(
            detected=True, failure_type="boundary_break",
            clarity=0.70, trigger_price=all_candles[-1].close, trigger_candle_idx=-1,
        )
        pattern = _make_pattern(ub=all_candles[-1].close - 0.01, lb=all_candles[-1].close - 0.07)
        c1h = make_bullish_trend_5m(48)
        setup = evaluate_continuation(all_candles, c1h, _make_trend_bias(), pattern, failure, settings)
        assert setup.stop_loss < setup.entry_price

    def test_volatility_regime_populated(self, settings):
        trend = make_bullish_trend_5m(50)
        corr = make_descending_channel(20, start_price=trend[-1].close, offset=50)
        all_candles = trend + corr
        from src.strategy.continuation_engine import FailureSignal
        failure = FailureSignal(True, "boundary_break", 0.65, all_candles[-1].close, -1)
        pattern = _make_pattern(ub=all_candles[-1].close - 0.01)
        c1h = make_bullish_trend_5m(48)
        setup = evaluate_continuation(all_candles, c1h, _make_trend_bias(), pattern, failure, settings)
        assert setup.volatility_regime in (
            "compressed_structured", "compressed_chop", "normal", "expanding", "chaotic", "unknown"
        )
