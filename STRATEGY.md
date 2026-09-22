# Strategy & risk rules

## Prime directive
Never lose more than the cash put in. Enforced in code: long-only, never short, never
leveraged, never options. The bot can only buy ETFs with settled cash and sell ETFs it holds.

## The portfolio (preset `balanced`)
Universe: 34 liquid, commission-free, fractional ETFs (US indices and sectors,
international, bonds, gold/silver/commodities/dollar), plus the 2x index funds SSO/QLD
for the `aggressive` preset. No single stocks.

1. **Core (50%)**: the strongest of SPY / QQQ / EFA by 3-6-12-month momentum, held while
   it is above its 150-day moving average, otherwise T-bills.
2. **Momentum rotation (50%)**: score each ETF by the average of its 3-, 6- and 12-month
   total returns (the last month is excluded: 1-month returns mean-revert). Eligible =
   positive score **and** price above its 150-day average. Hold the top 8,
   inverse-volatility weighted; a holding keeps its slot while it ranks in the top 11.
   (If the core's index is also a rotation pick, the two slices add up; the 35% cap applies
   to the rotation's slice only.)
   Five staggered tranches on a 10-day cycle, so a fifth of the sleeve rebalances every
   other day. A holding is dropped the day it breaks its 150-day average.
3. **Caps**: 35% per ETF and 40% per economic cluster in the rotation.
4. **Defensive**: anything not invested sits in `BIL` (T-bills).

These settings were chosen for the goal "lose money less often" (`python backtest.py
--grid7`): 50% core, 8 names and a 150-day filter improved losing-month and
losing-12-month frequency in all three windows tested, versus the earlier 30% / 6 / 200-day.

## The evidence (`reports/backtest.md`, `reports/validation.md`)
Daily bars 2008–2026, fills at the close, 5 bps slippage per side, $0 commissions,
dividends reinvested; SSO/QLD use their real price histories (fees and decay included).

| 2008 → 2026 | **balanced** | **aggressive** | SPY |
|---|---:|---:|---:|
| Yearly return | +9.8% | +15.6% | +11.4% |
| $1,000 became | $5,800 | $15,000 | $7,500 |
| Sharpe | 0.79 | 0.83 | 0.65 |
| Max drawdown | -18% | -28% | -52% |
| Losing months | 38% | 37% | – |
| Losing 12-month stretches | 22% | 22% | – |
| Losing calendar years | 4 of 19 | 4 of 19 | 4 of 19 |
| Worst year | -12% (2022) | -17% (2022) | -36% (2008) |
| Out-of-sample 2017+ | +13.1% | +20.0% | +15.4% |

Versus the previous settings (30% core, 6 names, 200-day), measured on the same corrected
code: losing years 5 → 4 of 19, losing 12-month stretches 27% → 24% (2015+) and 26% → 23%
(2017+), max drawdown -20% → -18%, return about the same. The cost: the worst 12-month
stretch is a little deeper (-13.5% vs -11.2% since 2017). The `aggressive` preset gets the
same settings: same return as before, losing 12-month stretches 26% → 22%, drawdown -31% → -28%.

What no setting can do: make losing months rare. About a third of months are down for
anything that earns stock-like returns, SPY included. What the strategy controls is how
deep and how long the losses are.

- **Walk-forward**: parameters picked on 2008–2016 alone hold up on 2017–2026 (Sharpe
  in the out-of-sample column of `reports/validation.md` §1 and §6).
- **Bootstrap** (1,000 synthetic 5-year paths): 3% chance of a negative 5-year stretch;
  see `reports/validation.md` §4 for drawdown odds.
- **The catch**: `balanced` trails SPY in most bull markets. `aggressive` is the preset
  that beats it, with bigger swings. The `aggressive` kill switch sits at 45%.

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
