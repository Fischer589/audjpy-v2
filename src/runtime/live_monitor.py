"""Live monitor -- orchestration layer.

Responsibilities:
  1. Poll IBKR for new 5M candles at the configured interval
  2. Detect duplicate candles (single compact log line, no processing)
  3. Run the deterministic evaluation chain on each NEW candle
  4. Log the compact [summary] block for every cycle
  5. Route accepted signals to paper execution
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import datetime
from typing import Optional

from src.config import BotSettings
from src.data.candle_feed import IbkrCandleFeed
from src.models.signal import EvaluationResult
from src.risk.risk_manager import RiskManager
from src.strategy.continuation_engine import detect_failure, evaluate_continuation
from src.strategy.corrective_structure import detect_correction
from src.strategy.signal_quality import score_signal
from src.strategy.trend_bias import analyze_htf_trend

logger = logging.getLogger(__name__)

_STOPPED = False


def _handle_sigterm(signum: int, frame: object) -> None:
    global _STOPPED
    logger.info("[monitor] SIGTERM received -- stopping after current cycle")
    _STOPPED = True


_SESSION_HOURS: dict[str, tuple[int, int]] = {
    "tokyo":    (0,  9),
    "london":   (7,  16),
    "new_york": (13, 22),
}


def _in_allowed_session(settings: BotSettings) -> bool:
    now_utc = datetime.utcnow()
    h = now_utc.hour
    for session_name, (start, end) in _SESSION_HOURS.items():
        if session_name in settings.allowed_sessions and start <= h < end:
            return True
    return False


def _in_rollover(settings: BotSettings) -> bool:
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # type: ignore
    tz = ZoneInfo(settings.rollover_timezone)
    now_local = datetime.now(tz)
    t = now_local.strftime("%H:%M")
    return settings.rollover_no_trade_start <= t <= settings.rollover_no_trade_end


class LiveMonitor:
    def __init__(
        self,
        settings: BotSettings,
        feed: IbkrCandleFeed,
        risk: RiskManager,
    ) -> None:
        self.settings = settings
        self.feed = feed
        self.risk = risk
        self._last_5m_ts: Optional[datetime] = None
        self._last_dup_log_ts: Optional[datetime] = None

    def run(self) -> None:
        global _STOPPED
        _STOPPED = False
        signal.signal(signal.SIGTERM, _handle_sigterm)

        logger.info(
            "[monitor] Starting. symbol=%s mode=%s poll=%ds",
            self.settings.symbol,
            self.settings.execution_mode,
            self.settings.poll_interval_seconds,
        )

        while not _STOPPED:
            try:
                self._poll()
            except KeyboardInterrupt:
                logger.info("[monitor] KeyboardInterrupt -- stopping")
                break
            except Exception as exc:
                logger.error("[monitor] Unhandled error: %s", exc, exc_info=True)

            time.sleep(self.settings.poll_interval_seconds)

        logger.info("[monitor] Stopped.")

    def _poll(self) -> Optional[EvaluationResult]:
        candles_5m = self.feed.get_5m_candles(limit=self.settings.correction_lookback_5m + 10)

        if not candles_5m:
            logger.warning("[monitor] No 5M candles returned")
            return None

        latest_ts = candles_5m[-1].timestamp

        if latest_ts == self._last_5m_ts:
            if self._last_dup_log_ts != latest_ts:
                logger.debug("[monitor] duplicate 5M ts=%s -- skipping", latest_ts.isoformat())
                self._last_dup_log_ts = latest_ts
            return None

        self._last_5m_ts = latest_ts

        candles_1h = self.feed.get_1h_candles(limit=self.settings.trend_lookback_1h + 10)
        candles_4h = self.feed.get_4h_candles(limit=self.settings.trend_lookback_4h + 10)

        result = self._evaluate(candles_5m, candles_1h, candles_4h)

        logger.info("%s", result.compact_log())

        if result.accepted:
            self._on_signal(result)

        return result

    def _evaluate(
        self,
        candles_5m: list,
        candles_1h: list,
        candles_4h: list,
    ) -> EvaluationResult:
        s = self.settings

        trend = analyze_htf_trend(candles_1h, candles_4h, s)
        if trend.direction == "neutral" or trend.confidence < s.min_trend_confidence:
            return self._rejected(
                trend, "descending_channel", 0.0, 0.0, False, "none", 0.0, 0.0, "normal", 0.0,
                gate="trend_confidence", value=trend.confidence,
            )

        pattern = detect_correction(candles_5m, trend.direction, s)
        if pattern.pattern_type == "none":
            return self._rejected(
                trend, "none", 0.0, 0.0, False, "none", 0.0, 0.0, "normal", 0.0,
                gate="no_corrective_structure", value=0.0,
            )

        if pattern.exhaustion_score < s.min_exhaustion_score:
            return self._rejected(
                trend, pattern.pattern_type,
                pattern.compression_score, pattern.exhaustion_score,
                False, "none", 0.0, 0.0, "normal", 0.0,
                gate="exhaustion_score", value=pattern.exhaustion_score,
            )

        failure = detect_failure(candles_5m, pattern, trend.direction, s)
        if not failure.detected:
            return self._rejected(
                trend, pattern.pattern_type,
                pattern.compression_score, pattern.exhaustion_score,
                False, "none", 0.0, 0.0, "normal", 0.0,
                gate="no_failure_signal", value=0.0,
            )

        setup = evaluate_continuation(candles_5m, candles_1h, trend, pattern, failure, s)

        if setup.continuation_prob < s.min_continuation_prob:
            return self._rejected(
                trend, pattern.pattern_type,
                pattern.compression_score, pattern.exhaustion_score,
                True, failure.failure_type, failure.clarity,
                setup.continuation_prob, setup.volatility_regime, 0.0,
                gate="continuation_prob", value=setup.continuation_prob,
            )

        quality = score_signal(trend, pattern, failure, setup, s)

        if quality.override_reject:
            return self._rejected(
                trend, pattern.pattern_type,
                pattern.compression_score, pattern.exhaustion_score,
                True, failure.failure_type, failure.clarity,
                setup.continuation_prob, setup.volatility_regime, quality.confidence,
                gate=quality.override_reason, value=quality.confidence,
            )

        if quality.confidence < s.min_confidence:
            return self._rejected(
                trend, pattern.pattern_type,
                pattern.compression_score, pattern.exhaustion_score,
                True, failure.failure_type, failure.clarity,
                setup.continuation_prob, setup.volatility_regime, quality.confidence,
                gate="signal_confidence", value=quality.confidence,
            )

        if not _in_allowed_session(s):
            return self._rejected(
                trend, pattern.pattern_type,
                pattern.compression_score, pattern.exhaustion_score,
                True, failure.failure_type, failure.clarity,
                setup.continuation_prob, setup.volatility_regime, quality.confidence,
                gate="session_filter", value=0.0,
            )

        if _in_rollover(s):
            return self._rejected(
                trend, pattern.pattern_type,
                pattern.compression_score, pattern.exhaustion_score,
                True, failure.failure_type, failure.clarity,
                setup.continuation_prob, setup.volatility_regime, quality.confidence,
                gate="rollover_window", value=0.0,
            )

        spread = self.feed.get_live_spread_pips()
        if spread > s.max_spread_pips:
            return self._rejected(
                trend, pattern.pattern_type,
                pattern.compression_score, pattern.exhaustion_score,
                True, failure.failure_type, failure.clarity,
                setup.continuation_prob, setup.volatility_regime, quality.confidence,
                gate="spread_filter", value=spread,
            )

        can_trade, risk_reason = self.risk.can_trade()
        if not can_trade:
            return self._rejected(
                trend, pattern.pattern_type,
                pattern.compression_score, pattern.exhaustion_score,
                True, failure.failure_type, failure.clarity,
                setup.continuation_prob, setup.volatility_regime, quality.confidence,
                gate=risk_reason, value=0.0,
            )

        account_balance = self.settings.starting_balance
        pos = self.risk.size_position(setup.entry_price, setup.stop_loss, account_balance)

        return EvaluationResult(
            trend_direction=trend.direction,
            trend_strength=trend.strength,
            trend_confidence=trend.confidence,
            corrective_pattern=pattern.pattern_type,
            compression_score=pattern.compression_score,
            exhaustion_score=pattern.exhaustion_score,
            failure_detected=True,
            failure_type=failure.failure_type,
            failure_clarity=failure.clarity,
            continuation_prob=setup.continuation_prob,
            volatility_regime=setup.volatility_regime,
            confidence=quality.confidence,
            direction=setup.direction,
            entry_price=setup.entry_price,
            stop_loss=setup.stop_loss,
            take_profit=setup.take_profit,
            risk_reward=setup.risk_reward,
            position_units=pos.units_1k,
            accepted=True,
        )

    @staticmethod
    def _rejected(
        trend, pattern_type, compression, exhaustion,
        failure_detected, failure_type, failure_clarity,
        continuation_prob, volatility_regime, confidence,
        gate: str, value: Optional[float],
    ) -> EvaluationResult:
        return EvaluationResult(
            trend_direction=trend.direction,
            trend_strength=trend.strength,
            trend_confidence=trend.confidence,
            corrective_pattern=pattern_type,
            compression_score=compression,
            exhaustion_score=exhaustion,
            failure_detected=failure_detected,
            failure_type=failure_type,
            failure_clarity=failure_clarity,
            continuation_prob=continuation_prob,
            volatility_regime=volatility_regime,
            confidence=confidence,
            accepted=False,
            rejection_gate=gate,
            rejection_value=value,
        )

    def _on_signal(self, result: EvaluationResult) -> None:
        logger.info(
            "[signal] ACCEPTED %s  entry=%.3f sl=%.3f tp=%.3f rr=%.1f units=%d",
            result.direction, result.entry_price or 0,
            result.stop_loss or 0, result.take_profit or 0,
            result.risk_reward or 0, result.position_units or 0,
        )
        self.risk.record_trade_open()

        if self.settings.paper_submit_orders:
            self._submit_paper_order(result)

    def _submit_paper_order(self, result: EvaluationResult) -> None:
        try:
            from ib_insync import MarketOrder, LimitOrder, StopOrder  # type: ignore
            ib = self.feed.connection.ib
            contract = self.feed.connection.contract

            action = "BUY" if result.direction == "long" else "SELL"
            qty = (result.position_units or 1) * 1000

            parent = MarketOrder(action, qty)
            parent.transmit = False

            sl_action = "SELL" if action == "BUY" else "BUY"
            sl = StopOrder(sl_action, qty, result.stop_loss)
            sl.parentId = parent.orderId
            sl.transmit = False

            tp = LimitOrder(sl_action, qty, result.take_profit)
            tp.parentId = parent.orderId
            tp.transmit = True

            ib.placeOrder(contract, parent)
            ib.placeOrder(contract, sl)
            ib.placeOrder(contract, tp)

            logger.info("[order] Paper bracket submitted: %s %.5f sl=%.5f tp=%.5f",
                        action, result.entry_price, result.stop_loss, result.take_profit)
        except Exception as exc:
            logger.error("[order] Failed to submit paper order: %s", exc)
