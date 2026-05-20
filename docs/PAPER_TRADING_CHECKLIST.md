# Paper Trading Checklist

## Phase 1 -- Pre-Deploy

- [ ] TWS or IB Gateway installed and running
- [ ] Paper trading account logged in (NOT live)
- [ ] API settings: Enable ActiveX and Socket Clients = checked
- [ ] API settings: Socket port = 4002
- [ ] API settings: Read-Only API = unchecked
- [ ] Python 3.11+ installed and in PATH
- [ ] Git installed and in PATH
- [ ] `config/settings.local.yaml` created

## Phase 2 -- Deploy

- [ ] `deploy\windows\deploy.ps1` runs with no errors
- [ ] All 14 steps complete
- [ ] All pytest tests pass
- [ ] Bot window opens without errors

## Phase 3 -- Log-Only Verification (~1 day)

Set `paper_submit_orders: false`, `logging.level: DEBUG`

- [ ] Bot connects to IBKR
- [ ] `[summary]` blocks appearing every poll cycle
- [ ] Duplicate candle messages are single DEBUG lines
- [ ] Rejection reasons are specific (Gate name + value)
- [ ] Session filter working (no evaluations outside session hours)
- [ ] Rollover block working

## Phase 4 -- Paper Orders

Set `paper_submit_orders: true`

- [ ] First accepted signal shows bracket order in log
- [ ] Order visible in TWS paper account
- [ ] SL and TP legs present
- [ ] After 3 trades: `max_trades_per_day` limit hit

## Phase 5 -- Ongoing Monitoring

**Daily:**
- [ ] Check logs for ERROR-level messages
- [ ] Review `[summary]` block rejection reasons
- [ ] Verify paper account P&L matches bot R tracking

**Monthly:**
- [ ] Review win rate and realized R:R
- [ ] Tune `min_exhaustion_score` if bad setups are slipping through
- [ ] Update `pip_value_usd_per_1k_units` if AUDJPY rate has moved significantly

## Red Flags -- Stop and Investigate

- No `[summary]` blocks after 30 minutes during session hours
- All signals rejected at Gate 1 with confidence 0.0
- SL sizes 3x larger than expected
- `[order] ERROR` in logs
- Bot process disappeared without shutdown log line

## Before Going Live (minimum 3 months paper)

- [ ] Positive expectancy over 3+ months
- [ ] Drawdown never exceeded 8%
- [ ] Realized R:R above 1.5
- [ ] Win rate above 40%
- [ ] Start live with 25% of intended position size
