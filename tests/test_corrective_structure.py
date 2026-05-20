"""Tests for corrective_structure.py."""
from __future__ import annotations
import pytest

from src.strategy.corrective_structure import detect_correction, _NONE
from tests.fixtures.candles import (
    make_bullish_trend_5m,
    make_descending_channel,
    make_compression,
    make_breakout_candle,
)


class TestNoCorrection:
    def test_trending_candles_return_none(self, settings):
        candles = make_bullish_trend_5m(60)
        result = detect_correction(candles, "bullish", settings)
        assert result.pattern_type == "none"

    def test_neutral_direction_returns_none(self, settings):
        candles = make_bullish_trend_5m(60)
        result = detect_correction(candles, "neutral", settings)
        assert result.pattern_type == "none"

    def test_too_few_candles_returns_none(self, settings):
        from tests.fixtures.candles import make_descending_channel
        candles = make_descending_channel(3)
        result = detect_correction(candles, "bullish", settings)
        assert result.pattern_type == "none"


class TestDescendingChannel:
    def _build(self, settings):
        trend = make_bullish_trend_5m(30, step=0.02)
        correction = make_descending_channel(25, start_price=trend[-1].close, offset=30)
        return trend + correction

    def test_descending_channel_detected(self, settings):
        candles = self._build(settings)
        result = detect_correction(candles, "bullish", settings)
        assert result.pattern_type in ("descending_channel", "wedge", "tight_pullback")

    def test_correction_has_positive_quality(self, settings):
        candles = self._build(settings)
        result = detect_correction(candles, "bullish", settings)
        if result.pattern_type != "none":
            assert result.quality > 0.0

    def test_correction_fields_in_range(self, settings):
        candles = self._build(settings)
        result = detect_correction(candles, "bullish", settings)
        if result.pattern_type != "none":
            assert 0.0 <= result.compression_score <= 1.0
            assert 0.0 <= result.exhaustion_score <= 1.0
            assert 0.0 <= result.overlap_score <= 1.0
            assert result.candle_count >= settings.min_correction_bars


class TestCompression:
    def _build(self, settings):
        trend = make_bullish_trend_5m(30, step=0.02)
        compr = make_compression(20, start_price=trend[-1].close - 0.05, offset=30)
        return trend + compr

    def test_compression_detected(self, settings):
        candles = self._build(settings)
        result = detect_correction(candles, "bullish", settings)
        assert result.pattern_type in ("compression", "descending_channel", "tight_pullback", "drift")

    def test_compression_has_high_overlap(self, settings):
        candles = self._build(settings)
        result = detect_correction(candles, "bullish", settings)
        if result.pattern_type == "compression":
            assert result.overlap_score > 0.40

    def test_exhaustion_increases_with_compression(self, settings):
        trend = make_bullish_trend_5m(30, step=0.02)
        loose = make_compression(20, start_price=trend[-1].close - 0.05, tightening=0.0005, offset=30)
        tight = make_compression(20, start_price=trend[-1].close - 0.05, tightening=0.003, offset=30)
        result_loose = detect_correction(trend + loose, "bullish", settings)
        result_tight = detect_correction(trend + tight, "bullish", settings)
        if result_loose.pattern_type != "none" and result_tight.pattern_type != "none":
            assert result_tight.exhaustion_score >= result_loose.exhaustion_score - 0.05


class TestBoundaryValues:
    def test_upper_bound_above_lower_bound(self, settings):
        trend = make_bullish_trend_5m(30, step=0.02)
        correction = make_descending_channel(25, start_price=trend[-1].close, offset=30)
        result = detect_correction(trend + correction, "bullish", settings)
        if result.pattern_type != "none":
            assert result.upper_bound > result.lower_bound

    def test_atr_ratio_positive(self, settings):
        trend = make_bullish_trend_5m(30, step=0.02)
        correction = make_descending_channel(25, start_price=trend[-1].close, offset=30)
        result = detect_correction(trend + correction, "bullish", settings)
        if result.pattern_type != "none":
            assert result.atr_ratio > 0.0
