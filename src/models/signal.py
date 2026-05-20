"""Evaluation result and compact log format."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvaluationResult:
    trend_direction: str
    trend_strength: float
    trend_confidence: float

    corrective_pattern: str
    compression_score: float
    exhaustion_score: float

    failure_detected: bool
    failure_type: str
    failure_clarity: float

    continuation_prob: float
    volatility_regime: str
    confidence: float

    direction: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None
    position_units: Optional[int] = None

    accepted: bool = False
    rejection_gate: Optional[str] = None
    rejection_value: Optional[float] = None

    notes: list[str] = field(default_factory=list)

    def compact_log(self) -> str:
        lines = ["[summary]"]
        lines.append(f"trend={self.trend_direction}  strength={self.trend_strength:.2f}  conf={self.trend_confidence:.2f}")
        lines.append(f"corrective={self.corrective_pattern}")
        lines.append(f"compression={self.compression_score:.2f}  exhaustion={self.exhaustion_score:.2f}")

        if self.failure_detected:
            lines.append(f"failure={self.failure_type}  clarity={self.failure_clarity:.2f}")
        else:
            lines.append("failure=none")

        lines.append(f"continuation={self.continuation_prob:.2f}")
        lines.append(f"volatility={self.volatility_regime}")
        lines.append(f"confidence={self.confidence:.2f}")

        if self.accepted:
            rr = f"{self.risk_reward:.1f}" if self.risk_reward else "n/a"
            lines.append(f"decision=accepted  dir={self.direction}  rr={rr}")
        else:
            if self.rejection_value is not None:
                lines.append(f"decision=rejected  gate={self.rejection_gate}  value={self.rejection_value:.3f}")
            else:
                lines.append(f"decision=rejected  gate={self.rejection_gate}")

        return "\n".join(lines)
