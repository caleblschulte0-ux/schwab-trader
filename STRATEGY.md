# Strategy & risk rules

## Prime directive
Never lose more than the cash put in. Enforced in code: long-only, never short, never
leveraged, never options. The bot can only buy ETFs with settled cash and sell ETFs it holds.

## The portfolio (preset `balanced`)
Universe: 34 liquid, commission-free, fractional ETFs (US indices and sectors,
international, bonds, gold/silver/commodities/dollar). No single stocks.

1. **Core (30%)**: SPY while it is above its 200-day moving average, otherwise T-bills.
   Plain trend-timed market beta. (`growth` preset: QQQ instead.)
2. **Momentum rotation (70%)**: score each ETF by the average of its 3-, 6- and 12-month
   total returns (the last month is excluded: 1-month returns mean-revert). Eligible =
   positive score **and** price above its 200-day average. Every 10 trading days hold the
   top 6, inverse-volatility weighted; a holding keeps its slot while it ranks in the top 8.
   Between rebalances a holding is dropped only when it breaks its 200-day average.
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
| CAGR | +9.4% | +11.4% |
| Sharpe | **0.82** | 0.65 |
| Max drawdown | **-17%** | -52% |
| Worst year | -3% (2018) | -36% (2008) |

- **Walk-forward**: parameters selected on 2008–2016 alone, then run untouched on 2017–2026:
  Sharpe 0.97 out-of-sample vs 0.68 in-sample. Not overfit.
- **Sensitivity**: Sharpe stays 0.63–0.84 across top-N 3–8 and every lookback set. A plateau.
- **Bootstrap** (1,000 synthetic 5-year paths): median CAGR +9.6%, 5th percentile +1.4%;
  3% chance of a negative 5-year stretch; 2% chance of a -30% drawdown.
- **The catch**: it beats SPY in only ~6% of rolling 3-year windows. It is built to compound
  through bear markets with a third of the drawdown, not to beat the index in a bull run.
  If you want more upside and accept more concentration, use the `growth` preset
  (+10.2% CAGR, Sharpe 0.84, -18% max DD).

## Hard guardrails (in `bot.py`)
- Weights sum to ≤ 100%; buys capped to settled cash; sells before buys.
- Only universe symbols are touched. Anything else in the account is ignored.
- One strategy step per trading day; re-runs the same day only reconcile.
- Trades only inside the last `trade_window_min` (120) minutes of a session.
- **Kill switch** at `max_drawdown_halt` (30%) below the high-water mark: liquidate and
  halt until a human deletes `halted` from `signals/state.json`. Why 30% and not 20%: the
  bootstrap shows a 20% halt would fire in ~18% of normal 5-year stretches and sell the low.
- Broker-side `trading_blocked` aborts the run with a non-zero exit.

## Account notes
- Simulator: starts at $1,000 (`executor.sim_start_cash`), 5 bps slippage, book in
  `signals/sim_account.json`. Delete that file to restart.
- Alpaca paper: reset the paper balance to $1,000 or set `MAX_CAPITAL=1000`.
- Live cash account: proceeds settle T+1; the bot only buys with settled cash.
