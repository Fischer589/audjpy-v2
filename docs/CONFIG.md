# Config Reference

All parameters live in `config/settings.yaml`. Override locally in `config/settings.local.yaml` (git-ignored). Environment variables prefixed `BOT_` override both files.

---

## IBKR Connection

```yaml
ibkr:
  host: 127.0.0.1
  port: 4002           # paper: 4002, live: 4001
  client_id: 1
```

---

## Trend Gate

```yaml
min_trend_confidence: 0.50   # Gate threshold. Raise to 0.65+ for stricter filtering.
trend_lookback_4h: 30        # 4H candles for trend analysis
trend_lookback_1h: 48        # 1H candles for trend analysis
swing_pivot_bars: 3          # Bars each side to qualify a swing point
require_1h_4h_alignment: true  # Penalise if 1H and 4H disagree
```

---

## Corrective Structure Gate

```yaml
correction_lookback_5m: 80   # Max 5M candles scanned
min_correction_bars: 8       # Min bars to qualify
max_correction_bars: 70      # Corrections longer than this ignored
```

---

## Exhaustion Gate

```yaml
min_exhaustion_score: 0.30   # Raise to 0.50 for stricter (cleaner compressions only)
atr_compression_threshold: 0.70  # ATR ratio below = compressed
atr_chaotic_threshold: 1.60      # ATR ratio above = chaotic (hard skip)
```

---

## Risk Management

```yaml
risk_per_trade_pct: 1.0      # % of account balance risked per trade
max_trades_per_day: 3        # Hard daily trade limit
max_daily_loss_r: 2.0        # Stop trading if daily loss exceeds 2R
stop_loss_atr_multiplier: 1.5
take_profit_rr: 2.5          # R:R ratio
```

---

## Safety / Execution

```yaml
paper_submit_orders: false   # Set true in settings.local.yaml to enable paper orders
live_trading: false          # Must be explicitly set true for live
```

---

## Three-Layer Config Merge

1. `config/settings.yaml` -- committed defaults
2. `config/settings.local.yaml` -- local VPS overrides (git-ignored)
3. `BOT_*` environment variables -- runtime overrides
