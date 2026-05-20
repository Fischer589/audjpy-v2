"""IBKR candle feed with pacing guard."""
from __future__ import annotations

import logging
import threading
import time as _time
from datetime import date, datetime
from typing import Optional

from src.config import BotSettings
from src.models.candle import Candle
from src.runtime.ibkr_connection import IbkrConnection

logger = logging.getLogger(__name__)

_PACING_LOCK = threading.Lock()
_LAST_REQUEST_TS: Optional[float] = None
_PACING_INTERVAL = 0.65


class _PacingGuard:
    def __enter__(self) -> "_PacingGuard":
        global _LAST_REQUEST_TS
        with _PACING_LOCK:
            now = _time.monotonic()
            if _LAST_REQUEST_TS is not None:
                elapsed = now - _LAST_REQUEST_TS
                if elapsed < _PACING_INTERVAL:
                    _time.sleep(_PACING_INTERVAL - elapsed)
            _LAST_REQUEST_TS = _time.monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        pass


_PACE = _PacingGuard()


def ibkr_bar_to_candle(bar: object) -> Candle:
    raw = getattr(bar, "date", None)
    if isinstance(raw, datetime):
        ts = raw
    elif isinstance(raw, date) and not isinstance(raw, datetime):
        ts = datetime(raw.year, raw.month, raw.day)
    elif isinstance(raw, str):
        for fmt in ("%Y%m%d %H:%M:%S", "%Y%m%d"):
            try:
                ts = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unrecognised IBKR date string: {raw!r}")
    else:
        raise TypeError(f"Unexpected bar.date type: {type(raw)}")
    return Candle(
        timestamp=ts,
        open=float(bar.open),
        high=float(bar.high),
        low=float(bar.low),
        close=float(bar.close),
        volume=float(getattr(bar, "volume", 0.0)),
    )


class IbkrCandleFeed:
    def __init__(
        self,
        settings: BotSettings,
        connection: IbkrConnection,
        candle_limit: int = 100,
    ) -> None:
        if candle_limit <= 0:
            raise ValueError("candle_limit must be positive")
        self.settings = settings
        self.connection = connection
        self.candle_limit = candle_limit

    def get_5m_candles(self, limit: Optional[int] = None) -> list[Candle]:
        return self._fetch("5 mins", limit or self.candle_limit)

    def get_1h_candles(self, limit: Optional[int] = None) -> list[Candle]:
        return self._fetch("1 hour", limit or self.candle_limit)

    def get_4h_candles(self, limit: Optional[int] = None) -> list[Candle]:
        return self._fetch("4 hours", limit or self.candle_limit)

    def get_live_spread_pips(self) -> float:
        try:
            ticker = self.connection.ib.reqMktData(self.connection.contract, "", False, False)
            self.connection.ib.sleep(0.5)
            bid, ask = ticker.bid, ticker.ask
            self.connection.ib.cancelMktData(self.connection.contract)
            if bid and ask and bid > 0 and ask > 0:
                return round((ask - bid) / 0.01, 2)
        except Exception:
            pass
        return self.settings.spread_pips

    def _fetch(self, bar_size: str, limit: int) -> list[Candle]:
        duration = self._duration_for(bar_size, limit)
        end_dt = datetime.now().strftime("%Y%m%d %H:%M:%S")
        with _PACE:
            bars = self.connection.ib.reqHistoricalData(
                self.connection.contract,
                endDateTime=end_dt,
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="MIDPOINT",
                useRTH=False,
                formatDate=1,
                keepUpToDate=False,
            )
        candles = [ibkr_bar_to_candle(b) for b in list(bars)[-limit:]]
        logger.debug("[feed] %s  fetched=%d", bar_size, len(candles))
        return candles

    def _duration_for(self, bar_size: str, limit: int) -> str:
        if bar_size == "5 mins":
            hours = max(limit * 5 // 60 + 1, 2)
            return f"{hours} H" if hours <= 24 else f"{hours // 24 + 1} D"
        if bar_size == "1 hour":
            days = max(limit // 24 + 1, 2)
            return f"{days} D"
        if bar_size == "4 hours":
            days = max(limit * 4 // 24 + 2, 3)
            return f"{days} D"
        return "2 D"
