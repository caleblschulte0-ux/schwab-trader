# Analyst review — week of 2026-11-07

_Covers the sim/paper book as of the last close, 2026-11-06._

## What it holds, and why

Still the **guarded_growth** preset, and more defensive than last week:

- **~79% in BIL (T-bills).** Two things stack up here: (1) the **core sleeve**
  (normally 50%, in whichever of SPY/QQQ/EFA leads on 3-6-12 month momentum) shows
  `regime.core: null` — none of the three is above its 150-day average right now, so
  the entire core slice defaults to T-bills instead of holding SPY/SSO like it did last
  week. (2) The **credit-stress signal** (`HYG/IEF` below their 50-day average) is
  still active, halving the momentum sleeve's normal risk budget. Both effects push the
  same direction, which is why defensive cash jumped from 56.9% last week to ~79% now.
- **~21% in the momentum rotation, 8 of 8 target names**: `DBC, USO, XBI, XLB, XLE,
  XLF, XLP, XLV` — energy, materials, financials, staples, healthcare and commodities,
  i.e. the same defensive/value tilt as last week, now joined by `XLF`. Tranche 2 of 5
  just rebalanced in `XLB` and `XLF`; no name is near the 35% per-ETF cap or 40%
  cluster cap. Breadth (share of the universe above its own trend) is 44.8%, up from
  37.9% last week even as exposure fell — the extra defensiveness is coming from the
  core/credit overlays, not from fewer ETFs qualifying.
- The mean-reversion sleeve is still empty, as it is in the 18-year backtest (0
  round-trips) — an empty MR book is normal, not a sign anything's broken.

## Live vs. backtest

The 18.8-year backtest for this exact preset/code path shows +12.7% CAGR, Sharpe 0.79,
a -22.0% max drawdown, and losing months 40% of the time (the strategy doc's own table
quotes +13.2%/yr for `guarded_growth`, +16.8% out-of-sample). The live sim book is now
about 6.5 weeks old (since 2026-09-22): equity has gone $1,000 → $929.35, **-7.06%
total**, with a **-9.5%** max drawdown — a fourth losing stretch, deeper than last
week's -7.1%, but still well inside the backtest's normal range of rough patches. The
"-44.8% CAGR" and "-3.49 Sharpe" printed in `track_record.md` are just this ~6-week
loss annualized — not a meaningful rate over such a short window, and not something to
read as a verdict on the strategy one way or the other.

Trade-level stats are weak again: 42 closed round-trips, 29% win rate, profit factor
0.08, expectancy -1.64/trade. Most of the damage is concentrated in `QLD` (the 2x
Nasdaq fund), which the kill-switch-free leveraged-core rule exposed to a sharp pullback
before the core rule dropped it — a single QLD lot opened 2026-09-24 and closed
2026-10-30 lost $35.42 on its own. Execution cost still averages +5.0 bps vs. the
decision price, matching the backtest's assumed 5 bps almost exactly, so this remains a
market-direction problem, not a slippage or fill-quality problem.

## Anomalies checked — none found this week

1. **Holdings reconcile with targets.** Both `signals/targets.json` and
   `signals/holdings.json` list the same 9 symbols (`BIL` plus the 8 momentum names),
   and position weights line up with target weights within a point or two — the small
   gaps (e.g. `XBI` at 2.07% target vs. ~1.77% actual) are explained by price drift
   since the rebalance, not a reconciliation problem. Last week's missing-`XLB` gap is
   resolved — `XLB` is back in both target and holdings this week.
2. **Not halted.** `signals/state.json` has no `halted` key. Drawdown from the
   high-water mark ($1,029.15) to current equity ($929.35) is 9.7%, nowhere near the
   40% kill-switch threshold the strategy doc's table lists for `guarded_growth`.
3. **Not stalled.** Last run timestamp 2026-11-07T00:04:46Z corresponds to decision
   date 2026-11-06 — a normal one-day lag for an end-of-close run, with `rebalanced:
   true` and an active tranche note for the day.
4. **Wash sales continue to accumulate** — 19 loss-sale/rebuy pairs within 30 days now
   logged (up from 17 last week), still concentrated in `QLD` (6 of the losses,
   including the -$35.42 lot above). Immaterial in this sim/IRA context, but worth
   remembering if this book is ever run in a taxable account: the tranche-driven churn
   will keep generating real wash-sale basis adjustments.
5. **News layer still has nothing to score** — zero overrides logged. Normal at this
   stage, nowhere close to the ~20-override sample size needed to judge whether it adds
   or costs value.

## Bottom line

The portfolio is doing exactly what the rulebook calls for in a weak-momentum,
credit-stressed regime: both the core and rotation sleeves lean defensive, and the
book is now ~79% T-bills. The live loss so far (-7.06% over 6.5 weeks, -9.5% drawdown
from the high-water mark) is unpleasant but small, well inside guardrails, and still
too short a sample to compare meaningfully against the 18-year backtest. Nothing here
looks like a bug — last week's target/holdings gap in `XLB` has resolved itself, and
everything else reconciles cleanly against the strategy's own rules.
