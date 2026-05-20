"""Bot configuration.

Three-layer merge (last wins):
  1. config/settings.yaml       -- tracked defaults
  2. config/settings.local.yaml -- gitignored VPS overrides
  3. Environment variables       -- secrets / final overrides
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BotSettings:
    # Identity
    symbol: str = "AUDJPY"
    broker: str = "ibkr"
    execution_mode: str = "paper"
    live_trading: bool = False

    # IBKR connection
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 4002
    ibkr_client_id: int = 1

    # Polling
    poll_interval_seconds: int = 30

    # Trend gate
    min_trend_confidence: float = 0.50
    trend_lookback_4h: int = 30
    trend_lookback_1h: int = 48
    swing_pivot_bars: int = 3
    require_1h_4h_alignment: bool = True

    # Corrective structure gate
    correction_lookback_5m: int = 80
    min_correction_bars: int = 8
    max_correction_bars: int = 70

    # Exhaustion gate
    min_exhaustion_score: float = 0.30

    # Continuation gate
    min_continuation_prob: float = 0.50

    # Quality gate
    min_confidence: float = 0.52

    # Volatility
    atr_baseline_period: int = 20
    atr_compression_threshold: float = 0.70
    atr_chaotic_threshold: float = 1.60

    # Risk
    risk_per_trade_pct: float = 1.0
    max_trades_per_day: int = 3
    max_daily_loss_r: float = 2.0
    stop_loss_atr_multiplier: float = 1.5
    take_profit_rr: float = 2.5
    starting_balance: float = 10000.0
    pip_value_usd_per_1k_units: float = 0.067

    # Filters
    max_spread_pips: float = 2.5
    spread_pips: float = 1.0

    allowed_sessions: tuple = ("tokyo", "london", "new_york")
    rollover_no_trade_start: str = "17:00"
    rollover_no_trade_end: str = "18:00"
    rollover_timezone: str = "America/New_York"

    news_filter_enabled: bool = True
    news_blackout_before_minutes: int = 30
    news_blackout_after_minutes: int = 15
    news_fail_safe: str = "allow"
    news_calendar_path: str = "config/news_calendar.json"

    # Output
    log_file_path: str = "logs/live.log"
    save_chart_snapshots: bool = False
    snapshot_directory: str = "snapshots/"
    journal_directory: str = "journals/"
    verbose_logging: bool = True

    # Paper execution
    paper_submit_orders: bool = False
    approval_required: bool = True
    approval_timeout_minutes: int = 5

    # Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @classmethod
    def from_mapping(cls, d: dict[str, Any]) -> "BotSettings":
        def _bool(key: str, default: bool) -> bool:
            v = d.get(key, default)
            if isinstance(v, str):
                return v.lower() in ("true", "1", "yes")
            return bool(v)

        def _float(key: str, default: float) -> float:
            return float(d.get(key, default))

        def _int(key: str, default: int) -> int:
            return int(d.get(key, default))

        def _str(key: str, default: str) -> str:
            return str(d.get(key, default))

        def _list(key: str, default: list) -> tuple:
            v = d.get(key, default)
            if isinstance(v, (list, tuple)):
                return tuple(v)
            return tuple(default)

        ibkr = d.get("ibkr", {}) if isinstance(d.get("ibkr"), dict) else {}

        return cls(
            symbol=_str("symbol", "AUDJPY"),
            broker=_str("broker", "ibkr"),
            execution_mode=_str("execution_mode", "paper"),
            live_trading=_bool("live_trading", False),
            ibkr_host=ibkr.get("host", _str("ibkr_host", "127.0.0.1")),
            ibkr_port=int(ibkr.get("port", _int("ibkr_port", 4002))),
            ibkr_client_id=int(ibkr.get("client_id", _int("ibkr_client_id", 1))),
            poll_interval_seconds=_int("poll_interval_seconds", 30),
            min_trend_confidence=_float("min_trend_confidence", 0.50),
            trend_lookback_4h=_int("trend_lookback_4h", 30),
            trend_lookback_1h=_int("trend_lookback_1h", 48),
            swing_pivot_bars=_int("swing_pivot_bars", 3),
            require_1h_4h_alignment=_bool("require_1h_4h_alignment", True),
            correction_lookback_5m=_int("correction_lookback_5m", 80),
            min_correction_bars=_int("min_correction_bars", 8),
            max_correction_bars=_int("max_correction_bars", 70),
            min_exhaustion_score=_float("min_exhaustion_score", 0.30),
            min_continuation_prob=_float("min_continuation_prob", 0.50),
            min_confidence=_float("min_confidence", 0.52),
            atr_baseline_period=_int("atr_baseline_period", 20),
            atr_compression_threshold=_float("atr_compression_threshold", 0.70),
            atr_chaotic_threshold=_float("atr_chaotic_threshold", 1.60),
            risk_per_trade_pct=_float("risk_per_trade_pct", 1.0),
            max_trades_per_day=_int("max_trades_per_day", 3),
            max_daily_loss_r=_float("max_daily_loss_r", 2.0),
            stop_loss_atr_multiplier=_float("stop_loss_atr_multiplier", 1.5),
            take_profit_rr=_float("take_profit_rr", 2.5),
            starting_balance=_float("starting_balance", 10000.0),
            pip_value_usd_per_1k_units=_float("pip_value_usd_per_1k_units", 0.067),
            max_spread_pips=_float("max_spread_pips", 2.5),
            spread_pips=_float("spread_pips", 1.0),
            allowed_sessions=_list("allowed_sessions", ["tokyo", "london", "new_york"]),
            rollover_no_trade_start=_str("rollover_no_trade_start", "17:00"),
            rollover_no_trade_end=_str("rollover_no_trade_end", "18:00"),
            rollover_timezone=_str("rollover_timezone", "America/New_York"),
            news_filter_enabled=_bool("news_filter_enabled", True),
            news_blackout_before_minutes=_int("news_blackout_before_minutes", 30),
            news_blackout_after_minutes=_int("news_blackout_after_minutes", 15),
            news_fail_safe=_str("news_fail_safe", "allow"),
            news_calendar_path=_str("news_calendar_path", "config/news_calendar.json"),
            log_file_path=_str("log_file_path", "logs/live.log"),
            save_chart_snapshots=_bool("save_chart_snapshots", False),
            snapshot_directory=_str("snapshot_directory", "snapshots/"),
            journal_directory=_str("journal_directory", "journals/"),
            verbose_logging=_bool("verbose_logging", True),
            paper_submit_orders=_bool("paper_submit_orders", False),
            approval_required=_bool("approval_required", True),
            approval_timeout_minutes=_int("approval_timeout_minutes", 5),
            telegram_enabled=_bool("telegram_enabled", False),
            telegram_bot_token=_str("telegram_bot_token", ""),
            telegram_chat_id=_str("telegram_chat_id", ""),
        )

    def validate(self) -> None:
        if self.symbol != "AUDJPY":
            raise ValueError(f"Unsupported symbol: {self.symbol}")
        if self.execution_mode not in ("paper", "live"):
            raise ValueError(f"execution_mode must be 'paper' or 'live', got: {self.execution_mode}")
        if self.live_trading and self.execution_mode != "live":
            raise ValueError("live_trading=true requires execution_mode=live")
        if not (0 < self.risk_per_trade_pct <= 5):
            raise ValueError(f"risk_per_trade_pct out of range (0,5]: {self.risk_per_trade_pct}")
        if self.stop_loss_atr_multiplier <= 0:
            raise ValueError("stop_loss_atr_multiplier must be positive")
        if self.take_profit_rr <= 0:
            raise ValueError("take_profit_rr must be positive")
        if self.news_fail_safe not in ("allow", "block"):
            raise ValueError(f"news_fail_safe must be 'allow' or 'block'")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("PyYAML required: pip install pyyaml") from exc
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)
    return loaded if isinstance(loaded, dict) else {}


def load_settings(
    config_path: Path | str = Path("config/settings.yaml"),
    local_path: Path | str | None = None,
    env_prefix: str = "BOT",
) -> BotSettings:
    """Load settings from YAML files then override with env vars."""
    base = _load_yaml(Path(config_path))
    local = _load_yaml(Path(local_path) if local_path else Path("config/settings.local.yaml"))
    base.update(local)

    prefix = (env_prefix.upper() + "_") if env_prefix else ""
    for key, val in os.environ.items():
        if not prefix or key.upper().startswith(prefix):
            env_key = key[len(prefix):].lower() if prefix else key.lower()
            base[env_key] = val

    settings = BotSettings.from_mapping(base)
    settings.validate()
    return settings
