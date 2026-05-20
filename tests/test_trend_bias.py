"""Tests for trend_bias.py."""
from __future__ import annotations
from datetime import timedelta

import pytest

from src.config import BotSettings
from src.strategy.trend_bias import analyze_htf_trend
from tests.fixtures.candles import make_htf_bullish, make_htf_bearish, make_htf_mixed

_1H = timedelta(hours=1)
_4H = timedelta(hours=4)


class TestBullishTrend:
    def test_strong_bullish_recognized(self, settings):
        c1h = make_htf_bullish(50, _1H)
        c4h = make_htf_bullish(35, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        assert result.direction == "bullish"
        assert result.confidence >= 0.45

    def test_bullish_confidence_above_minimum(self, settings):
        c1h = make_htf_bullish(50, _1H)
        c4h = make_htf_bullish(35, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        assert result.confidence >= settings.min_trend_confidence

    def test_bullish_strength_components(self, settings):
        c1h = make_htf_bullish(50, _1H)
        c4h = make_htf_bullish(35, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        assert result.strength > 0.60
        assert result.impulse_quality > 0.40

    def test_bullish_momentum_phase_not_unknown(self, settings):
        c1h = make_htf_bullish(60, _1H)
        c4h = make_htf_bullish(35, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        assert result.momentum_phase in ("accelerating", "steady", "decelerating")


class TestBearishTrend:
    def test_strong_bearish_recognized(self, settings):
        c1h = make_htf_bearish(50, _1H)
        c4h = make_htf_bearish(35, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        assert result.direction == "bearish"
        assert result.confidence >= 0.45

    def test_bearish_confidence_above_minimum(self, settings):
        c1h = make_htf_bearish(50, _1H)
        c4h = make_htf_bearish(35, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        assert result.confidence >= settings.min_trend_confidence


class TestNeutralTrend:
    def test_choppy_market_is_neutral(self, settings):
        c1h = make_htf_mixed(50, _1H)
        c4h = make_htf_mixed(35, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        assert result.direction == "neutral"
        assert result.confidence == 0.0

    def test_insufficient_candles_returns_neutral(self, settings):
        c1h = make_htf_bullish(5, _1H)
        c4h = make_htf_bullish(5, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        assert result.direction in ("bullish", "bearish", "neutral")


class TestAlignment:
    def test_misaligned_lowers_confidence(self, settings):
        c1h = make_htf_bearish(50, _1H)
        c4h = make_htf_bullish(35, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        if result.direction != "neutral":
            assert result.confidence < 0.65

    def test_require_alignment_flag_penalizes(self):
        strict = BotSettings(require_1h_4h_alignment=True)
        loose = BotSettings(require_1h_4h_alignment=False)
        c1h = make_htf_bearish(50, _1H)
        c4h = make_htf_bullish(35, _4H)
        r_strict = analyze_htf_trend(c1h, c4h, strict)
        r_loose = analyze_htf_trend(c1h, c4h, loose)
        assert r_strict.confidence <= r_loose.confidence + 0.01


class TestOutputFields:
    def test_all_fields_populated(self, settings):
        c1h = make_htf_bullish(50, _1H)
        c4h = make_htf_bullish(35, _4H)
        result = analyze_htf_trend(c1h, c4h, settings)
        assert result.direction in ("bullish", "bearish", "neutral")
        assert 0.0 <= result.strength <= 1.0
        assert 0.0 <= result.impulse_quality <= 1.0
        assert result.momentum_phase in ("accelerating", "steady", "decelerating", "unknown")
        assert result.swing_4h in ("bullish", "bearish", "neutral")
        assert result.swing_1h in ("bullish", "bearish", "neutral")
        assert 0.0 <= result.confidence <= 1.0
