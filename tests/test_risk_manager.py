"""Tests for risk_manager.py."""
from __future__ import annotations
import pytest
from datetime import date

from src.config import BotSettings
from src.risk.risk_manager import RiskManager, DailyState


class TestCanTrade:
    def test_fresh_state_allows_trade(self, settings):
        rm = RiskManager(settings)
        ok, reason = rm.can_trade()
        assert ok
        assert reason == ""

    def test_max_trades_per_day_hit(self):
        s = BotSettings(max_trades_per_day=2)
        rm = RiskManager(s)
        rm.daily.trades_taken = 2
        ok, reason = rm.can_trade()
        assert not ok
        assert "max_trades_per_day" in reason

    def test_max_daily_loss_hit(self):
        s = BotSettings(max_daily_loss_r=2.0)
        rm = RiskManager(s)
        rm.daily.realized_r = -2.0
        ok, reason = rm.can_trade()
        assert not ok
        assert "max_daily_loss_r" in reason

    def test_partial_loss_still_allows(self):
        s = BotSettings(max_daily_loss_r=2.0, max_trades_per_day=3)
        rm = RiskManager(s)
        rm.daily.realized_r = -1.5
        rm.daily.trades_taken = 1
        ok, _ = rm.can_trade()
        assert ok


class TestPositionSizing:
    def test_basic_sizing(self, settings):
        rm = RiskManager(settings)
        pos = rm.size_position(entry=90.00, stop_loss=89.80, account_balance=10000.0)
        assert pos.ok
        assert pos.units_1k >= 1
        assert pos.sl_pips == pytest.approx(20.0, abs=0.1)

    def test_risk_usd_matches_pct(self, settings):
        rm = RiskManager(settings)
        pos = rm.size_position(entry=90.00, stop_loss=89.80, account_balance=10000.0)
        expected_risk = 10000.0 * settings.risk_per_trade_pct / 100.0
        assert pos.risk_usd <= expected_risk * 1.05

    def test_zero_sl_distance_fails(self, settings):
        rm = RiskManager(settings)
        pos = rm.size_position(entry=90.00, stop_loss=90.00, account_balance=10000.0)
        assert not pos.ok
        assert pos.reason == "zero_sl_distance"

    def test_short_stop_above_entry(self, settings):
        rm = RiskManager(settings)
        pos = rm.size_position(entry=90.00, stop_loss=90.20, account_balance=10000.0)
        assert pos.ok
        assert pos.sl_pips == pytest.approx(20.0, abs=0.1)

    def test_larger_balance_gives_more_units(self, settings):
        rm = RiskManager(settings)
        pos_small = rm.size_position(entry=90.00, stop_loss=89.80, account_balance=10000.0)
        pos_large = rm.size_position(entry=90.00, stop_loss=89.80, account_balance=100000.0)
        assert pos_large.units_1k > pos_small.units_1k


class TestDailyState:
    def test_record_trade_increments_count(self, settings):
        rm = RiskManager(settings)
        rm.record_trade_open()
        assert rm.daily.trades_taken == 1
        rm.record_trade_open()
        assert rm.daily.trades_taken == 2

    def test_record_close_updates_r(self, settings):
        rm = RiskManager(settings)
        rm.record_trade_close(2.5)
        assert rm.daily.realized_r == pytest.approx(2.5)
        rm.record_trade_close(-1.0)
        assert rm.daily.realized_r == pytest.approx(1.5)
