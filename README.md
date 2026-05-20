# AUDJPY V2 — HTF Trend Continuation Bot

Paper-trading bot for AUDJPY on Interactive Brokers. Trades **HTF trend continuation after corrective structure failure** — not a breakout or BOS/SMC bot.

---

## Strategy in One Paragraph

The bot identifies the dominant 1H/4H trend using EMA alignment and swing structure voting. It then monitors 5-minute price action for a corrective structure (descending channel, wedge, flat pullback, or compressed drift) against that trend. When the correction shows exhaustion — overlapping candles, slowing velocity, tightening range — the bot watches for a failure event: boundary break, failed re-entry, acceptance above/below structure, or a reclaim. Only then does it evaluate continuation probability and entry quality. Trades are only taken when all gates pass cleanly.

---

## Quick Start

```powershell
# Windows VPS — one command deploy
.\deploy\windows\deploy.ps1 -BotDir "C:\bots\audjpy-v2"
```

See [`deploy/windows/DEPLOYMENT.md`](deploy/windows/DEPLOYMENT.md) for the full 14-step guide.

---

## Architecture

```
src/
  models/
    candle.py           -- Candle dataclass with computed properties
    signal.py           -- EvaluationResult with compact_log()
  config.py             -- BotSettings + 3-layer config merge
  strategy/
    trend_bias.py       -- HTF trend direction + confidence
    corrective_structure.py  -- Channel/wedge/compression detection
    continuation_engine.py   -- Failure detection + continuation setup
    signal_quality.py   -- Final quality score + hard overrides
  data/
    candle_feed.py      -- IBKR candle fetcher with pacing guard
  risk/
    risk_manager.py     -- Position sizing + daily risk limits
  runtime/
    ibkr_connection.py  -- ib_insync connection wrapper
    live_monitor.py     -- Main evaluation loop
main.py                 -- Entry point
```

---

## Evaluation Chain (deterministic, always in this order)

```
1. HTF Trend        -- EMA + swing votes on 1H and 4H
2. Corrective       -- Linear regression channel on 5M
3. Compression      -- ATR ratio + overlap + velocity decay
4. Failure/Reclaim  -- Boundary break, failed re-entry, acceptance, reclaim
5. Continuation     -- Directional probability + SL/TP
6. Volatility       -- compressed_structured vs dead_chop vs chaotic
7. Quality Score    -- Weighted gate scores (hard overrides applied first)
8. Trade Decision   -- Accept or reject with exact gate + value
```

Every rejection logs the exact gate that failed and the failing value.

---

## Volatility Regimes

| Regime | ATR Ratio | Overlap | Body Trend | Action |
|---|---|---|---|---|
| `compressed_structured` | < threshold | High | Decaying | **GOOD** — trade setup |
| `compressed_chop` | < threshold | High | Flat/random | **BAD** — skip |
| `normal` | ~1.0 | Medium | Any | Proceed normally |
| `expanding` | > 1.2 | Low | Growing | Proceed normally |
| `chaotic` | > chaotic threshold | Any | Any | **Skip** |

---

## Configuration

Primary config: `config/settings.yaml`  
Local overrides: `config/settings.local.yaml` (not committed)

See [`docs/CONFIG.md`](docs/CONFIG.md) for every parameter.

---

## Running

```powershell
# Standard run
python main.py

# With custom config dir
python main.py --config config --local config/settings.local.yaml

# Dry run (evaluation only, no orders)
# Set paper_submit_orders: false in settings.local.yaml
```

---

## Safety

- Paper-only by default (`paper_submit_orders: false`)
- Live execution disabled (`live_trading: false`)
- Max 3 trades/day, max 2R daily drawdown
- Rollover no-trade window enforced (17:00-18:00 NY time)
- Session filter: Tokyo + London + New York only

---

## Tests

```powershell
python -m pytest tests/ -v
```

73 tests across 6 test files. All use synthetic candle fixtures — no IBKR connection required.

---

## Links

- [Strategy Explanation](docs/STRATEGY.md)
- [Config Reference](docs/CONFIG.md)
- [Deployment Guide](deploy/windows/DEPLOYMENT.md)
- [Paper Trading Checklist](docs/PAPER_TRADING_CHECKLIST.md)
