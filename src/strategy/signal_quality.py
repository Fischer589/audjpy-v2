"""Final signal quality scorer.

Weights (sum to 1.0):
  - Trend confidence          0.30
  - Correction quality        0.25
  - Failure clarity           0.20
  - Continuation probability  0.15
  - Volatility alignment      0.10

Hard-reject overrides:
  - compressed_chop volatility regime
  - failure_type == 'none'
  - pattern_type == 'drift' with low exhaustion
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.strategy.trend_bias import TrendBias
from src.strategy.corrective_structure import CorrectivePattern
from src.strategy.continuation_engine import FailureSignal, ContinuationSetup
from src.config import BotSettings

logger = logging.getLogger(__name__)


@dataclass
class SignalQuality:
    confidence: float
    trend_component: float
    correction_component: float
    failure_component: float
    continuation_component: float
    volatility_component: float
    override_reject: bool
    override_reason: str


def score_signal(
    trend: TrendBias,
    pattern: CorrectivePattern,
    failure: FailureSignal,
    setup: ContinuationSetup,
    settings: BotSettings,
) -> SignalQuality:
    if not failure.detected:
        return SignalQuality(
            confidence=0.0,
            trend_component=0.0, correction_component=0.0,
            failure_component=0.0, continuation_component=0.0,
            volatility_component=0.0,
            override_reject=True, override_reason="no_failure_signal",
        )

    if setup.volatility_regime == "compressed_chop":
        return SignalQuality(
            confidence=0.0,
            trend_component=0.0, correction_component=0.0,
            failure_component=0.0, continuation_component=0.0,
            volatility_component=0.0,
            override_reject=True, override_reason="dead_chop_volatility",
        )

    if setup.volatility_regime == "chaotic":
        return SignalQuality(
            confidence=0.0,
            trend_component=0.0, correction_component=0.0,
            failure_component=0.0, continuation_component=0.0,
            volatility_component=0.0,
            override_reject=True, override_reason="chaotic_volatility",
        )

    if pattern.pattern_type == "drift" and pattern.exhaustion_score < 0.40:
        return SignalQuality(
            confidence=0.0,
            trend_component=0.0, correction_component=0.0,
            failure_component=0.0, continuation_component=0.0,
            volatility_component=0.0,
            override_reject=True, override_reason="drift_without_exhaustion",
        )

    t = trend.confidence
    c = pattern.quality
    f = failure.clarity
    p = setup.continuation_prob
    v = _vol_score(setup.volatility_regime)

    confidence = (
        t * 0.30
        + c * 0.25
        + f * 0.20
        + p * 0.15
        + v * 0.10
    )
    confidence = round(min(1.0, max(0.0, confidence)), 3)

    return SignalQuality(
        confidence=confidence,
        trend_component=round(t, 3),
        correction_component=round(c, 3),
        failure_component=round(f, 3),
        continuation_component=round(p, 3),
        volatility_component=round(v, 3),
        override_reject=False,
        override_reason="",
    )


def _vol_score(regime: str) -> float:
    return {
        "compressed_structured": 1.00,
        "normal": 0.70,
        "expanding": 0.55,
        "compressed_chop": 0.0,
        "chaotic": 0.0,
        "unknown": 0.45,
    }.get(regime, 0.45)
