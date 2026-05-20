# Strategy Explanation -- HTF Trend Continuation

## Core Premise

This bot does NOT trade breakouts, BOS/SMC, or reversals. It trades **the resumption of an already-established trend after a corrective pause**. The corrective phase must show exhaustion and then fail before the bot acts.

The edge: corrections into a strong trend compress and exhaust momentum, then fail quickly. The failure point is the highest-probability entry because the corrective crowd is trapped.

---

## Gate 1 -- HTF Trend Identification

**Method:** Four-vote system (4H EMA, 4H swing, 1H EMA, 1H swing)

- **Direction:** Majority of votes. Tie = neutral (no trade).
- **Confidence:** strength x 0.55 + impulse_quality x 0.30 + 0.15, modified by alignment factor and momentum phase
- **Gate threshold:** `min_trend_confidence` (default 0.50)

---

## Gate 2 -- Corrective Structure Detection

**Method:** Linear regression on 5M highs and lows from correction start

**Pattern types:** `descending_channel`, `wedge`, `tight_pullback`, `compression`, `drift`, `none`

**Gate:** Must be a recognized corrective pattern (not `none`).

---

## Gate 3 -- Compression / Exhaustion

**Overlap score:** Fraction of adjacent candle bodies that overlap (high = candles stacking without conviction)

**Velocity decay:** First-half vs second-half mean body size (positive = slowing momentum)

**Combined exhaustion:** `overlap x 0.5 + velocity_decay x 0.5`

**Gate threshold:** `min_exhaustion_score` (default 0.30)

---

## Gate 4 -- Corrective Failure / Reclaim

**Failure types:**
- `boundary_break` -- close beyond corrective channel in trend direction
- `failed_reentry` -- price re-enters then closes back out (trapped)
- `acceptance` -- 2+ consecutive candles accepted beyond boundary
- `reclaim` -- price returns above/below key corrective level

Binary gate -- no failure detected = chain stops here.

---

## Gate 5 -- Continuation Probability

```
prob = (trend_conf x 0.30 + correction_quality x 0.25 + failure_clarity x 0.25 + vol_bonus x 0.20) x momentum_mod
```

**Gate threshold:** `min_continuation_prob` (default 0.50)

---

## Gate 6 -- Volatility Context

| Regime | ATR Ratio | Overlap | Body Trend | Action |
|---|---|---|---|---|
| `compressed_structured` | < threshold | High | Decaying | GOOD |
| `compressed_chop` | < threshold | High | Flat | BAD -- skip |
| `normal` | ~1.0 | Medium | Any | Proceed |
| `expanding` | > 1.2 | Low | Growing | Proceed |
| `chaotic` | > chaotic_threshold | Any | Any | Skip |

---

## Gate 7 -- Signal Quality Score

**Hard overrides (immediate reject):**
- No failure detected
- `compressed_chop` regime
- `chaotic` regime
- Drift pattern without exhaustion (exhaustion < 0.40)

**Weighted score:**
```
score = trend x 0.30 + correction x 0.25 + failure x 0.20 + continuation x 0.15 + volatility x 0.10
```

**Gate threshold:** `min_confidence` (default 0.52)

---

## Entry, SL, TP

- **Entry:** Market at failure candle close
- **SL:** ATR(14) x `stop_loss_atr_multiplier`, placed below corrective low (long) or above corrective high (short)
- **TP:** SL distance x `take_profit_rr` (default 2.5:1)
- **Position size:** `risk_pct / (sl_pips x pip_value)` rounded to 1k-unit lots

---

## What This Bot Does NOT Do

- Does not trade reversals or counter-trend
- Does not use BOS as an entry signal
- Does not trade chop or range-bound markets
- Does not enter on ATR expansion alone
- Does not pyramid or add to positions
- Does not trade during rollover
