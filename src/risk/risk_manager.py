"""Risk management: position sizing + daily limits."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from src.config import BotSettings

logger = logging.getLogger(__name__)


@dataclass
class DailyState:
    trade_date: date = field(default_factory=date.today)
    trades_taken: int = 0
    realized_r: float = 0.0

    def reset_if_new_day(self) -> None:
        today = date.today()
        if today != self.trade_date:
            logger.info("[risk] New day %s -- resetting daily counters", today)
            self.trade_date = today
            self.trades_taken = 0
            self.realized_r = 0.0


@dataclass
class PositionSize:
    units_1k: int
    risk_usd: float
    sl_pips: float
    ok: bool
    reason: str


class RiskManager:
    def __init__(self, settings: BotSettings) -> None:
        self.settings = settings
        self.daily = DailyState()

    def can_trade(self) -> tuple[bool, str]:
        self.daily.reset_if_new_day()
        s = self.settings

        if self.daily.trades_taken >= s.max_trades_per_day:
            return False, f"max_trades_per_day={s.max_trades_per_day} reached"

        if self.daily.realized_r <= -s.max_daily_loss_r:
            return False, f"max_daily_loss_r={s.max_daily_loss_r} reached (current={self.daily.realized_r:.2f}R)"

        return True, ""

    def size_position(
        self,
        entry: float,
        stop_loss: float,
        account_balance: float,
    ) -> PositionSize:
        s = self.settings
        pip_size = 0.01

        sl_distance = abs(entry - stop_loss)
        sl_pips = sl_distance / pip_size

        if sl_pips < 1e-6:
            return PositionSize(units_1k=0, risk_usd=0.0, sl_pips=0.0, ok=False, reason="zero_sl_distance")

        risk_usd = account_balance * s.risk_per_trade_pct / 100.0
        lots = risk_usd / (sl_pips * s.pip_value_usd_per_1k_units)
        units_1k = max(1, int(lots))

        actual_risk = units_1k * sl_pips * s.pip_value_usd_per_1k_units

        return PositionSize(
            units_1k=units_1k,
            risk_usd=round(actual_risk, 2),
            sl_pips=round(sl_pips, 1),
            ok=True,
            reason="",
        )

    def record_trade_open(self) -> None:
        self.daily.reset_if_new_day()
        self.daily.trades_taken += 1
        logger.info("[risk] Trade opened. Daily count=%d", self.daily.trades_taken)

    def record_trade_close(self, r_multiple: float) -> None:
        self.daily.realized_r += r_multiple
        logger.info(
            "[risk] Trade closed %.2fR. Daily R=%.2f",
            r_multiple, self.daily.realized_r,
        )
