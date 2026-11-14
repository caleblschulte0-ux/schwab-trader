# Analyst review — week of 2026-11-14

_Covers the sim/paper book as of the last close, 2026-11-13._

## What it holds, and why

Still the **guarded_growth** preset, defensively positioned:

- **~52.5% in BIL (T-bills).** The **credit-stress signal** (`HYG/IEF` below their
  50-day average) is active, which per the strategy rules halves the risk budget for
  both sleeves (`regime.credit_stress: true`, `regime.exposure: 0.475`). That's why
  about half the book sits in cash-like T-bills rather than the 0% a calm regime would
  imply.
- **~25% core, in SSO.** The core sleeve picks the strongest of SPY/QQQ/EFA by 3-6-12
  month momentum while it's above its 150-day average; the `aggressive`/`guarded_growth`
  presets express that pick through its 2x leveraged twin (SPY → SSO, QQQ → QLD) per the
  strategy's universe rules. SPY currently leads and is above trend, so the core holds
  SSO at half its normal 50% weight (credit-stress halving).
- **~22.5% momentum rotation, 8 of 8 target names**: `DBC, USO, XBI, XLB, XLE, XLF,
  XLP, XLV` — energy, materials, financials, staples, healthcare/biotech and two
  commodity funds, a defensive/value tilt. Breadth (share of the universe above its own
  trend) is 55.2%, a healthy reading; no name is close to the 35% per-ETF or 40% cluster
  caps. The mean-reversion sleeve remains empty, as in the 18-year backtest (0
  round-trips) — normal, not a sign anything's broken.
- Executions over the past two weeks show the core repeatedly flipping SSO ↔ BIL
  (sold SSO 2026-11-05, bought back 2026-11-10) as the credit/momentum regime got
  reassessed day to day — expected tranche/core behavior, not churn from a bug.

## Live vs. backtest

`reports/backtest.md`, the 18.8-year run on this exact preset/code path, shows +12.5%
CAGR, Sharpe 0.78, Sortino 1.08, a -22.0% max drawdown, and losing months 40% of the
time. The live sim book is about 7.6 weeks old (since 2026-09-22): equity has gone
$1,000 → $933.62, **-6.64% total**, with a **-9.5%** max drawdown. The "-38.3% CAGR"
and "-3.00 Sharpe" in `track_record.md` are this ~7.6-week loss annualized — noise from
a tiny sample, not a meaningful rate, and well inside the kind of rough patch the
backtest's own losing-months/losing-12-month-stretch stats say to expect.

Trade-level stats remain weak: 44 closed round-trips, 27% win rate, profit factor
0.08, expectancy -1.57/trade. The single worst lot is still `QLD` (2x Nasdaq), opened
2026-09-24 and closed 2026-10-30 for -$35.42 (-15.34%) as the core rule caught a sharp
pullback before dropping it; a newer `SSO` lot added a second notable loss, -$12.37
(-5.38%), opened 2026-10-30 and closed 2026-11-05 — consistent with the
`alert.json` flag for that day (SPY -4.2%, QQQ -6.0%, XBI -6.5%), a broad one-day
drawdown already visible as the dip in the equity curve ($953.70 → $929.36). Execution
cost still averages +5.0 bps vs. the decision price, matching the backtest's assumed 5
bps almost exactly — this remains a market-direction problem, not a slippage problem.

## Anomalies checked

1. **Holdings mostly reconcile with targets, with one gap worth flagging.** Both
   `signals/targets.json` and `signals/holdings.json` list the same 10 symbols (`BIL`,
   `SSO`, and the 8 momentum names). Most weights line up within a point of target once
   price drift since the last rebalance is accounted for (e.g. `SSO` 25.0% target vs.
   25.4% actual, `XLV` 3.65% vs. 3.92%). `XLP` is the outlier: target 3.00% ($28.04)
   vs. actual 2.22% ($20.75), a ~26% dollar shortfall, bigger than anything else in the
   book. `signals/state.json`'s tranche detail explains it — the oldest of the 5
   staggered tranches (`days_since_rebalance: 9`) hasn't rotated into `XLP` yet, so only
   4 of 5 tranches currently hold it. That's the "five staggered tranches on a 10-day
   cycle" rule working as designed, not a reconciliation bug, but worth re-checking next
   week once that tranche rolls.
2. **Not halted.** `signals/state.json` has no `halted` key. Drawdown from the
   high-water mark ($1,029.15) to current equity ($933.62) is about 9.3%, far from the
   40% kill-switch threshold for `guarded_growth`.
3. **Not stalled.** Last run `2026-11-14T01:01:33Z` corresponds to decision date
   2026-11-13; `reports/today.md` shows a normal weekend no-op ("Outside trade window —
   refreshing snapshot only", next close 2026-11-16) rather than a broken run.
4. **News layer logged an elevated read, no override.** `signals/news_risk.json` shows
   `market_risk: 1` (hot inflation print, Fed hike signal, Nvidia leadership turmoil) —
   level 1 is "logged only" per the strategy's effect table, so no position changes are
   expected or seen. Zero overrides remain scored in `track_record.md`, still far short
   of the ~20-override sample needed to judge the news layer's value.
5. **Wash sales keep accumulating** — 22 loss-sale/rebuy pairs within 30 days now
   logged (up from 19 previously), still concentrated in `QLD` and the SSO/BIL core
   flips. Immaterial in this sim context, but a reminder that the tranche-driven churn
   generates real wash-sale basis adjustments in a taxable account.

## Bottom line

The book is doing what the rulebook calls for in a credit-stressed regime with one
clear momentum leader: half the risk budget is parked in BIL, the core holds SSO at
half weight, and the rotation sleeve runs its normal 8 names. The live loss so far
(-6.64% over 7.6 weeks, -9.5% drawdown from the high-water mark) is unpleasant but
small and inside the range the backtest says to expect; the short sample still makes
any annualized comparison meaningless. The only item to watch is `XLP`'s undersized
position versus target, which should resolve itself as the oldest tranche rotates in
over the next couple of rebalances — worth a one-line check next week to confirm it
closed the gap.
