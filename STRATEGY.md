# Strategy & risk rules

## Prime directive
Never lose more than the cash put in. Enforced in code: long-only, never short, never
leveraged, never options. The bot can only buy ETFs with settled cash and sell ETFs it holds.

## The portfolio (base settings; the live preset is `guarded_growth`, see the table below)
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

| 2008 → 2026 | conservative | **balanced** | guarded_growth | aggressive | SPY |
|---|---:|---:|---:|---:|---:|
| Yearly return | +8.1% | +9.8% | +13.2% | +15.6% | +11.4% |
| $1,000 became | $4,300 | $5,800 | $10,100 | $15,000 | $7,500 |
| Max drawdown | -14% | -18% | -22% | -28% | -52% |
| Losing 12-month stretches | 19% | 22% | 18% | 22% | – |
| Losing months | 38% | 38% | 40% | 37% | – |
| Out-of-sample 2017+ | +11.1% | +13.1% | +16.8% | +20.0% | +15.4% |
| Kill switch | 30% | 30% | 40% | 45% | – |

- **conservative** = balanced + the credit-stress signal (junk bonds lagging Treasuries → halve
  risk). Smallest drawdowns, lowest return.
- **guarded_growth** = aggressive + the credit-stress signal. Beats SPY in every window with
  under half its drawdown; fewer losing 12-month stretches than balanced, but slightly more
  losing months. A middle ground, not a free lunch.
- The credit signal is insurance: it trims 3–6 points off the worst drawdown and costs
  1.5–3 points of yearly return. It can't be tuned to be free; faster versions cost more.

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

## The news layer (defensive only)
Price data can't see an indictment, a war or an emergency Fed move until the market reacts.
So every trading day, before the executor runs, `news_brain.py` collects the last ~24 hours of
headlines and asks Claude to act as a risk officer for the portfolio the bot is about to hold.
It returns a market risk level and up to 3 vetoes, as strict JSON:

| Level | Meaning | Effect |
|---|---|---|
| 0 | normal (most days) | none |
| 1 | elevated | logged only |
| 2 | serious market-wide shock | risk assets ×0.75, rest to T-bills |
| 3 | crisis (9/11, Lehman, March 2020) | risk assets ×0.50 |
| veto | concrete new shock to a specific ETF (e.g. sanctions on a sector, scandal at a mega-cap that dominates a fund) | that ETF → T-bills for the day |

Why it can't pick buys: public news is priced within seconds, and the old bot that traded
headlines lost on 12 of 14 trades. Avoiding damage is where a daily news read can plausibly
help. Every claim must cite real headline ids or it is discarded. Overrides last one day;
the strategy's own state is untouched, so the book returns to normal when the news clears.

**It cannot be backtested** (there is no archive of what a model would have said on past
days), so it is scored live: each override records prices, and the next day the bot computes
whether it saved or cost money. The running tally is in `reports/track_record.md`. If it's
net negative after ~20 scored overrides, set `"news": {"enabled": false}` in `config.json`.

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
