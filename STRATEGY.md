# Strategy & risk rules

## Prime directive (unchanged)
Never lose more than the cash put in. Enforced in code: long-only, never short, never
leveraged, never options. The only thing the bot can do is buy ETFs with settled cash
and sell ETFs it holds.

## The strategy: ETF momentum rotation with a trend filter
Universe: 34 liquid, commission-free, fractional-share ETFs (US indices and sectors,
international, bonds, gold/silver/commodities/dollar). No single stocks: no earnings
gaps, no 2% spreads, no halts.

Every trading day, in the last two hours of the session:
1. **Score** each ETF by the average of its 3-, 6- and 12-month total returns.
   (The most recent month is deliberately excluded: 1-month returns mean-revert.)
2. **Filter**: only ETFs with a positive score **and** price above the 200-day moving
   average are eligible. If fewer than 5 qualify, the empty slots sit in `BIL`
   (1-3 month T-bills). In a bear market the book drifts to 100% T-bills by itself.
3. **Rebalance weekly** into the top 5, weighted inverse to their volatility (a 20%-vol
   commodity ETF gets a smaller slice than a 12%-vol bond ETF). A holding keeps its slot
   while it stays inside the top 7 (hysteresis) to cut churn. Between rebalances a
   holding is dropped only if it breaks below its 200-day average.
4. **Cap** any single ETF at 35% of capital.

Optional, off by default: a short-term mean-reversion sleeve (buy an equity ETF in an
uptrend after RSI(2) ≤ 10; exit on the snap-back). The backtest shows it dilutes the
momentum sleeve in every window tested, so it stays off unless you re-test it.

## What the backtest says (2008-01 → 2026-09, daily, 5 bps slippage, $0 commissions)
See `reports/backtest.md` for the full table. Headline:

| | Strategy | SPY buy & hold |
|---|---:|---:|
| CAGR | ~10% | ~11% |
| Sharpe | 0.72 | 0.65 |
| Max drawdown | **-19%** | **-52%** |
| 2008 | +7% | -36% |
| 2022 | -1% | -18% |

Read that honestly: over a period dominated by one of the greatest US bull markets in
history, a diversified trend-following rotation earns a bit less than buy-and-hold with
a third of the drawdown, and it makes money in the years that wreck buy-and-hold. It
will lag SPY in a straight-up year. It is meant to compound without ever handing you a
-50% year, not to beat the index every year.

Robustness (`python backtest.py --grid`): top-N of 4-7, weekly vs biweekly rebalance,
equal vs inverse-vol weights, hysteresis 0-4, with/without the cash proxy all land in the
same neighborhood. The one thing that clearly hurts is including the 1-month lookback.

## Hard guardrails (all in `bot.py`, none in prose)
- Long-only, no leverage: target weights always sum to ≤ 100%; buys are capped to settled cash.
- Sells execute before buys.
- Only symbols in the strategy universe are ever touched. Anything else in the account is ignored.
- One strategy step per trading day. A second run the same day only reconciles.
- Trades only inside the last `TRADE_WINDOW_MIN` (120) minutes of a session.
- **Kill switch**: if equity falls `MAX_DRAWDOWN_HALT` (20%) below its high-water mark,
  liquidate everything the bot manages and halt until a human deletes `halted` from
  `signals/state.json`. The backtest's worst drawdown is 19%, so this fires only if the
  live strategy is doing something history says it shouldn't.
- Broker-side blocks (`trading_blocked`) stop the run with a non-zero exit.

## Account notes
- Alpaca paper account: start it at $1,000 (Reset in the dashboard) or set the repo
  variable `MAX_CAPITAL=1000` so results are comparable to what you would fund live.
- Live cash account: proceeds settle T+1. The bot sells first and buys with the cash
  Alpaca reports as settled, so it will not generate good-faith violations; on a heavy
  rebalance day part of the buying may spill into the next day. That is fine.
- Fractional shares mean $1,000 is enough to hold five ETFs at proper weights.
