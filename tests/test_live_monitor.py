"""Tests for live_monitor.py evaluation chain."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from datetime import timedelta

from src.config import BotSettings
from src.risk.risk_manager import RiskManager
from src.runtime.live_monitor import LiveMonitor
from tests.fixtures.candles import (
    make_htf_bullish,
    make_htf_bearish,
    make_bullish_trend_5m,
    make_descending_channel,
    make_breakout_candle,
    make_duplicate_sequence,
)
_1H = timedelta(hours=1)
_4H = timedelta(hours=4)


def _make_monitor(settings=None):
    s = settings or BotSettings()
    feed = MagicMock()
    feed.get_live_spread_pips.return_value = 1.0
    risk = RiskManager(s)
    return LiveMonitor(s, feed, risk), feed


class TestDuplicateCandle:
    def test_duplicate_ts_returns_none(self):
        monitor, feed = _make_monitor()
        trend_5m = make_bullish_trend_5m(60, step=0.02)
        feed.get_5m_candles.return_value = trend_5m
        feed.get_1h_candles.return_value = make_htf_bullish(50, _1H)
        feed.get_4h_candles.return_value = make_htf_bullish(35, _4H)
        monitor._poll()
        result = monitor._poll()
        assert result is None

    def test_duplicate_candle_no_double_log(self):
        monitor, feed = _make_monitor()
        trend_5m = make_bullish_trend_5m(60, step=0.02)
        feed.get_5m_candles.return_value = trend_5m
        feed.get_1h_candles.return_value = make_htf_bullish(50, _1H)
        feed.get_4h_candles.return_value = make_htf_bullish(35, _4H)
        monitor._poll()
        r1 = monitor._poll()
        r2 = monitor._poll()
        assert r1 is None
        assert r2 is None

    def test_new_candle_after_duplicate_processes(self):
        from datetime import timedelta
        monitor, feed = _make_monitor()
        candles_v1 = make_bullish_trend_5m(60, step=0.02)
        feed.get_5m_candles.return_value = candles_v1
        feed.get_1h_candles.return_value = make_htf_bullish(50, _1H)
        feed.get_4h_candles.return_value = make_htf_bullish(35, _4H)
        monitor._poll()
        last = candles_v1[-1]
        from src.models.candle import Candle
        new_c = Candle(
            last.timestamp + timedelta(minutes=5),
            last.close, last.high + 0.01, last.low, last.close + 0.005,
        )
        candles_v2 = candles_v1[1:] + [new_c]
        feed.get_5m_candles.return_value = candles_v2
        result = monitor._poll()
        assert result is not None


class TestEvaluationChain:
    def _setup_bullish(self, monitor, feed, with_breakout=False):
        trend_5m = make_bullish_trend_5m(40, step=0.025)
        corr = make_descending_channel(25, start_price=trend_5m[-1].close, offset=40)
        all_5m = trend_5m + corr

        if with_breakout:
            from src.models.candle import Candle
            last = all_5m[-1]
            breakout = Candle(
                last.timestamp + timedelta(minutes=5),
                last.close,
                last.close + 0.10,
                last.close - 0.005,
                last.close + 0.08,
            )
            all_5m = all_5m + [breakout]

        feed.get_5m_candles.return_value = all_5m
        feed.get_1h_candles.return_value = make_htf_bullish(55, _1H)
        feed.get_4h_candles.return_value = make_htf_bullish(35, _4H)

    def test_trend_gate_rejection_on_neutral(self):
        from tests.fixtures.candles import make_htf_mixed
        monitor, feed = _make_monitor()
        trend_5m = make_bullish_trend_5m(60)
        feed.get_5m_candles.return_value = trend_5m
        feed.get_1h_candles.return_value = make_htf_mixed(55, _1H)
        feed.get_4h_candles.return_value = make_htf_mixed(35, _4H)
        result = monitor._poll()
        assert result is not None
        assert not result.accepted
        assert "trend" in result.rejection_gate

    def test_result_has_compact_log(self):
        monitor, feed = _make_monitor()
        self._setup_bullish(monitor, feed)
        result = monitor._poll()
        if result:
            log = result.compact_log()
            assert "[summary]" in log
            assert "trend=" in log
            assert "decision=" in log

    def test_evaluation_result_fields_populated(self):
        monitor, feed = _make_monitor()
        self._setup_bullish(monitor, feed)
        result = monitor._poll()
        if result:
            assert result.trend_direction in ("bullish", "bearish", "neutral")
            assert 0.0 <= result.trend_confidence <= 1.0
            assert 0.0 <= result.exhaustion_score <= 1.0
            assert 0.0 <= result.continuation_prob <= 1.0
            assert 0.0 <= result.confidence <= 1.0

    def test_rejection_gate_is_specific(self):
        monitor, feed = _make_monitor()
        self._setup_bullish(monitor, feed)
        result = monitor._poll()
        if result and not result.accepted:
            assert result.rejection_gate is not None
            assert len(result.rejection_gate) > 0


class TestCompactLogFormat:
    def test_accepted_log_contains_rr(self):
        from src.models.signal import EvaluationResult
        r = EvaluationResult(
            trend_direction="bullish", trend_strength=0.8, trend_confidence=0.72,
            corrective_pattern="descending_channel",
            compression_score=0.45, exhaustion_score=0.50,
            failure_detected=True, failure_type="boundary_break", failure_clarity=0.75,
            continuation_prob=0.68, volatility_regime="compressed_structured",
            confidence=0.65,
            direction="long", entry_price=90.12, stop_loss=89.90,
            take_profit=90.57, risk_reward=2.5,
            accepted=True,
        )
        log = r.compact_log()
        assert "accepted" in log
        assert "rr=" in log
        assert "[summary]" in log

    def test_rejected_log_shows_gate(self):
        from src.models.signal import EvaluationResult
        r = EvaluationResult(
            trend_direction="neutral", trend_strength=0.0, trend_confidence=0.25,
            corrective_pattern="none",
            compression_score=0.0, exhaustion_score=0.0,
            failure_detected=False, failure_type="none", failure_clarity=0.0,
            continuation_prob=0.0, volatility_regime="normal",
            confidence=0.0,
            accepted=False, rejection_gate="trend_confidence", rejection_value=0.25,
        )
        log = r.compact_log()
        assert "rejected" in log
        assert "trend_confidence" in log
        assert "0.250" in log
