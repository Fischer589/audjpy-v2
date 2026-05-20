"""IBKR connection wrapper."""
from __future__ import annotations

import logging
import time
from typing import Optional

from src.config import BotSettings

logger = logging.getLogger(__name__)


class IbkrConnection:
    def __init__(self, settings: BotSettings) -> None:
        self.settings = settings
        self._ib: Optional[object] = None
        self._contract: Optional[object] = None

    @property
    def ib(self) -> object:
        if self._ib is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._ib

    @property
    def contract(self) -> object:
        if self._contract is None:
            raise RuntimeError("Contract not qualified. Call connect() first.")
        return self._contract

    def connect(self, max_retries: int = 3, retry_delay: float = 5.0) -> None:
        from ib_insync import IB, Forex  # type: ignore

        s = self.settings
        ib = IB()

        for attempt in range(1, max_retries + 1):
            try:
                ib.connect(s.ibkr_host, s.ibkr_port, clientId=s.ibkr_client_id, readonly=True)
                contract = Forex("AUDJPY")
                ib.qualifyContracts(contract)
                self._ib = ib
                self._contract = contract
                logger.info(
                    "[ibkr] Connected %s:%d cid=%d  mode=%s",
                    s.ibkr_host, s.ibkr_port, s.ibkr_client_id, s.execution_mode,
                )
                return
            except Exception as exc:
                logger.warning("[ibkr] Connect attempt %d/%d failed: %s", attempt, max_retries, exc)
                if attempt < max_retries:
                    time.sleep(retry_delay)

        raise ConnectionError(
            f"Could not connect to IBKR at {s.ibkr_host}:{s.ibkr_port} "
            f"after {max_retries} attempts"
        )

    def disconnect(self) -> None:
        if self._ib is not None:
            try:
                self._ib.disconnect()
            except Exception:
                pass
            self._ib = None
            self._contract = None
            logger.info("[ibkr] Disconnected.")

    def is_connected(self) -> bool:
        return self._ib is not None and bool(self._ib.isConnected())

    def reconnect(self) -> None:
        self.disconnect()
        time.sleep(2.0)
        self.connect()
