"""Core candle model with computed price-action properties."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body_ratio(self) -> float:
        return self.body / self.range if self.range > 0 else 0.0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        return self.body_ratio < 0.15

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def upper_wick_ratio(self) -> float:
        return self.upper_wick / self.range if self.range > 0 else 0.0

    @property
    def lower_wick_ratio(self) -> float:
        return self.lower_wick / self.range if self.range > 0 else 0.0

    def overlaps_with(self, other: "Candle") -> bool:
        """True if this candle's body overlaps with other's body."""
        my_top = max(self.open, self.close)
        my_bot = min(self.open, self.close)
        ot_top = max(other.open, other.close)
        ot_bot = min(other.open, other.close)
        return my_top >= ot_bot and ot_top >= my_bot
