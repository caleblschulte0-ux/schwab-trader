# Strategy & risk rules

## Prime directive
Never lose more than the cash put in. Enforced in code: long-only, never short, never
leveraged, never options. The bot can only buy ETFs with settled cash and sell ETFs it holds.

## The portfolio (preset `balanced`)
Universe: 34 liquid, commission-free, fractional ETFs (US indices and sectors,
international, bonds, gold/silver/commodities/dollar). No single stocks.

1. **Core (30%)**: the strongest of SPY / QQQ / EFA by 3-6-12-month momentum, held while
   it is above its 200-day moving average, otherwise T-bills. Trend-timed market beta
   with a relative-momentum tilt. (`growth` preset: always QQQ. `us_only`: SPY/QQQ.)
2. **Momentum rotation (70%)**: score each ETF by the average of its 3-, 6- and 12-month
   total returns (the last month is excluded: 1-month returns mean-revert). Eligible =
   positive score **and** price above its 200-day average. Hold the top 6, inverse-volatility
   weighted; a holding keeps its slot while it ranks in the top 8. The sleeve is split into
   **five tranches** on a 10-day cycle, staggered two days apart, so one fifth of the book
   rebalances every other day: same rules, far less dependence on which day you started
   (validation §3). Between rebalances a holding is dropped the day it breaks its 200-day average.
3. **Caps**: 35% per ETF, 40% per economic cluster (energy, tech, treasuries, ...).
4. **Defensive**: any unfilled slot sits in `BIL` (1–3 month T-bills). In a bear market the
   book drifts to mostly T-bills by itself.

Implemented and switchable but OFF (the backtest says so; see `validation.md` §6):
mean-reversion sleeve, portfolio vol targeting, breadth regime switch, defensive asset
picked by momentum, daily rebalance.

## The evidence (`reports/backtest.md`, `reports/validation.md`)
Daily bars 2008–2026, fills at the close, 5 bps slippage per side, $0 commissions,
dividends reinvested, cash earns the T-bill ETF's return.

| | Strategy | SPY buy & hold |
|---|---:|---:|
| CAGR | +9.8% | +11.4% |
| Sharpe | **0.81** | 0.65 |
| Max drawdown | **-17%** | -52% |
| Worst year | -8% (2022) | -36% (2008) |
| 2008 | -0.3% | -36% |

- **Walk-forward**: parameters selected on 2008–2016 alone, then run untouched on 2017–2026:
  Sharpe 0.95 out-of-sample vs 0.61 in-sample. Not overfit.
- **Sensitivity**: Sharpe stays in a 0.6–0.85 plateau across top-N 3–8 and every lookback set.
- **Timing luck**: starting the cycle on five different days moves Sharpe only 0.78–0.81
  (it was 0.63–0.74 before tranching).
- **Bootstrap** (1,000 synthetic 5-year paths): median CAGR +9.6%, 5th percentile +1%;
  3% chance of a negative 5-year stretch; 2% chance of a -30% drawdown.
- **The catch**: it beats SPY in only ~8% of rolling 3-year windows. It is built to compound
  through bear markets with a third of the drawdown, not to beat the index in a bull run.
  More upside with more concentration: the `growth` preset (+10.1% CAGR, Sharpe 0.84).

## Want more return? The `aggressive` preset
Set `"preset": "aggressive"` in `config.json`. Half the book goes into a **2x daily
index fund** (SSO for the S&P 500, QLD for the Nasdaq-100, whichever index has stronger
momentum), held **only while that index is above its 200-day average**; the other half
runs the same momentum rotation. Still long-only with no margin: you cannot lose more
than you put in.

| 2008 → 2026 | balanced | **aggressive** | SPY |
|---|---:|---:|---:|
| CAGR | +9.9% | **+15.7%** | +11.4% |
| $1,000 became | $5,900 | **$15,200** | $7,500 |
| Sharpe | 0.81 | 0.81 | 0.65 |
| Max drawdown | -18% | **-31%** | -52% |
| Worst year | -8% | -15% | -36% |
| Out-of-sample 2017+ CAGR | +12.6% | **+20.1%** | +15.4% |

The Sharpe is identical: this is not a smarter strategy, it is the same one with the
risk dial turned up. Expect a 25–30% drawdown in a typical 5-year stretch (bootstrap
median -27%; 10% chance of -40%). The preset raises the kill switch to 45% for that
reason; at 30% it would fire in 37% of normal 5-year stretches. Numbers use the real
SSO/QLD price histories since 2008, so the funds' fees and daily-reset decay are included.
A volatility cap on top was tested and rejected: it cut returns to below SPY.

## Hard guardrails (in `bot.py`)
- Weights sum to ≤ 100%; buys capped to settled cash; sells before buys.
- Only universe symbols are touched. Anything else in the account is ignored.
- One strategy step per trading day; re-runs the same day only reconcile.
- Trades only inside the last `trade_window_min` (60) minutes of a session.
- **Kill switch** at `max_drawdown_halt` (30%) below the high-water mark: liquidate and
  halt until a human deletes `halted` from `signals/state.json`. Why 30% and not 20%: the
  bootstrap shows a 20% halt would fire in ~18% of normal 5-year stretches and sell the low.
- Broker-side `trading_blocked` aborts the run with a non-zero exit.
- **Stale-data guard**: no trades unless bars reach the previous session and live prices
  cover ≥80% of the universe. **Bad-tick guard**: a live price more than 25% away from the
  last close is treated as a glitch and replaced by the last close.
- **No same-day sells**: anything bought today cannot be sold today, so the bot can never
  create a day trade (pattern-day-trader rule) or a good-faith violation on a cash account.
- **Retry-safe orders**: every order carries a deterministic `client_order_id`; if a run is
  retried after a network error, Alpaca rejects the duplicate instead of buying twice.
- **Deposits and withdrawals** are read from the broker's activity log and shift the
  high-water mark, so moving money in or out can neither trigger nor mask the kill switch.
- **Live gate**: `DRY_RUN=false` is refused unless 20 clean paper runs are on record,
  `MAX_CAPITAL` is set, and `LIVE_CONFIRM` says `I UNDERSTAND THE RISKS`.

## Account notes
- Simulator: starts at $1,000 (`executor.sim_start_cash`), 5 bps slippage, book in
  `signals/sim_account.json`. Delete that file to restart.
- Alpaca paper: reset the paper balance to $1,000 or set `MAX_CAPITAL=1000`.
- Live cash account: proceeds settle T+1; the bot only buys with settled cash.
