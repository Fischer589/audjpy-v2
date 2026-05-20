"""Tests for signal_quality.py."""
from __future__ import annotations
import pytest

from src.strategy.signal_quality import score_signal
from src.strategy.trend_bias import TrendBias
from src.strategy.corrective_structure import CorrectivePattern
from src.strategy.continuation_engine import FailureSignal, ContinuationSetup


def _trend(direction="bullish", confidence=0.70):
    return TrendBias(
        direction=direction, strength=0.75, impulse_quality=0.65,
        momentum_phase="steady", swing_4h=direction, swing_1h=direction,
        ema_aligned_4h=True, ema_aligned_1h=True, htf_aligned=True,
        confidence=confidence,
    )


def _pattern(ptype="descending_channel", quality=0.75, exhaustion=0.45):
    return CorrectivePattern(
        pattern_type=ptype, upper_bound=90.08, lower_bound=90.02,
        upper_slope=-0.001, lower_slope=-0.001,
        compression_score=0.40, atr_ratio=0.65,
        overlap_score=0.55, exhaustion_score=exhaustion,
        candle_count=20, quality=quality,
    )


def _failure(detected=True, ftype="boundary_break", clarity=0.75):
    return FailureSignal(detected=detected, failure_type=ftype, clarity=clarity,
                         trigger_price=90.10, trigger_candle_idx=-1)


def _setup(vol="compressed_structured", prob=0.65):
    return ContinuationSetup(
        direction="long", entry_price=90.10, stop_loss=89.90,
        take_profit=90.55, risk_reward=2.5,
        continuation_prob=prob, volatility_regime=vol,
        atr_current=0.04, notes=[],
    )


class TestHardOverrides:
    def test_no_failure_returns_zero_confidence(self, settings):
        q = score_signal(_trend(), _pattern(), _failure(detected=False), _setup(), settings)
        assert q.override_reject
        assert q.confidence == 0.0
        assert q.override_reason == "no_failure_signal"

    def test_dead_chop_returns_zero(self, settings):
        q = score_signal(_trend(), _pattern(), _failure(), _setup(vol="compressed_chop"), settings)
        assert q.override_reject
        assert q.override_reason == "dead_chop_volatility"

    def test_chaotic_volatility_returns_zero(self, settings):
        q = score_signal(_trend(), _pattern(), _failure(), _setup(vol="chaotic"), settings)
        assert q.override_reject
        assert q.override_reason == "chaotic_volatility"

    def test_drift_without_exhaustion_rejected(self, settings):
        q = score_signal(
            _trend(),
            _pattern(ptype="drift", exhaustion=0.20),
            _failure(),
            _setup(),
            settings,
        )
        assert q.override_reject
        assert q.override_reason == "drift_without_exhaustion"


class TestWeightedScore:
    def test_high_quality_inputs_give_high_confidence(self, settings):
        q = score_signal(
            _trend(confidence=0.85),
            _pattern(quality=0.90, exhaustion=0.60),
            _failure(clarity=0.90),
            _setup(vol="compressed_structured", prob=0.75),
            settings,
        )
        assert not q.override_reject
        assert q.confidence > 0.60

    def test_low_quality_inputs_give_low_confidence(self, settings):
        q = score_signal(
            _trend(confidence=0.40),
            _pattern(quality=0.40, exhaustion=0.30),
            _failure(clarity=0.40),
            _setup(vol="normal", prob=0.40),
            settings,
        )
        assert q.confidence < 0.55

    def test_confidence_in_range(self, settings):
        q = score_signal(_trend(), _pattern(), _failure(), _setup(), settings)
        assert 0.0 <= q.confidence <= 1.0

    def test_all_components_populated(self, settings):
        q = score_signal(_trend(), _pattern(), _failure(), _setup(), settings)
        assert 0.0 <= q.trend_component <= 1.0
        assert 0.0 <= q.correction_component <= 1.0
        assert 0.0 <= q.failure_component <= 1.0
        assert 0.0 <= q.continuation_component <= 1.0
        assert 0.0 <= q.volatility_component <= 1.0

    def test_compressed_structured_higher_than_normal(self, settings):
        q_cs = score_signal(_trend(), _pattern(), _failure(), _setup(vol="compressed_structured"), settings)
        q_nm = score_signal(_trend(), _pattern(), _failure(), _setup(vol="normal"), settings)
        assert q_cs.confidence >= q_nm.confidence
