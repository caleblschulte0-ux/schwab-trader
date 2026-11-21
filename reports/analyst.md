# Analyst review — week of 2026-11-21

_Covers the sim/paper book through the last close, 2026-11-20. Top finding: the trading
decision loop appears stalled since 2026-11-13 — see "Anomalies checked" #1._

## What it holds, and why

Still the **guarded_growth** preset, defensively positioned — unchanged from last week
because, as detailed below, nothing has actually traded since:

- **~56% in BIL (T-bills)**, up from ~52.5% a week ago — not a new decision, just price
  drift. The **credit-stress signal** (`HYG/IEF` below their 50-day average) was active as
  of the last computed regime (`regime.credit_stress: true`, `regime.exposure: 0.475`),
  which halves the risk budget for both sleeves. BIL's share has grown further because the
  risk sleeve lost value this week while BIL didn't.
- **~22% core, in SSO** (was ~25% a week ago, $195.66 of $883.15 equity). The core sleeve
  held SPY's leveraged twin at half its normal 50% weight per the credit-stress halving;
  its share has shrunk because SSO itself is down **-15.9%** since entry, part of the
  broad market selloff this week (see below), not a rebalance.
- **~20% momentum rotation, the same 8 names as last week**: `DBC, USO, XBI, XLB, XLE,
  XLF, XLP, XLV` — energy, materials, financials, staples, healthcare/biotech and two
  commodity funds. These are the targets as of 2026-11-13 (`signals/targets.json`); no
  newer target set exists. Breadth at that date was 55.2%, a healthy reading, and no name
  was close to the 35%/40% caps — but that reading is now a week stale.
- The mean-reversion sleeve remains empty, as in the 18-year backtest (0 round-trips) —
  normal, not a sign anything's broken.

## Live vs. backtest

`reports/backtest.md` (18.8 years, same preset/code path) shows +12.6% CAGR, Sharpe
0.79, Sortino 1.08, a -22.0% max drawdown, and losing months 40% of the time. The live
sim book is now 8.4 weeks old (since 2026-09-22): equity has gone $1,000 → $882.76,
**-11.72% total**, with a **-14.0%** max drawdown (track_record.md) — worse than last
week's -6.64%/-9.5% read, and now the loss is concentrated in a single bad week:
$933.62 → $882.76 (-5.45%) between 2026-11-13 and 2026-11-20, which lines up with a
real, broad equity selloff (see `signals/alert.json` and `signals/news_risk.json`
below), not a strategy malfunction. The reported -53.8% "CAGR" / -4.80 "Sharpe" in
`track_record.md` are this 8-week loss annualized — still too short a sample to mean
anything on its own, though the magnitude is now large enough to be worth watching
rather than dismissing outright.

Trade-level stats are **unchanged from last week**: 44 closed round-trips, 27% win
rate, profit factor 0.08, expectancy -1.57/trade, 76 fills, $3,980 traded, average cost
+5.0 bps, and 22 wash-sale pairs. That's not a coincidence — it's corroborating
evidence for the stall below: zero trades have closed or opened in the past week.

## Anomalies checked

1. **The decision loop looks stalled since 2026-11-13 — the main item to flag.**
   `signals/state.json` shows `last_decision_date` and `last_trade_date` both stuck at
   `2026-11-13`, while `last_seen_date`/`last_run_utc` (2026-11-20T21:02:18Z) show the
   process is still being invoked daily. `signals/targets.json` carries the same
   2026-11-13 date and `"rebalanced": false`. `signals/executions.json` has no fills
   after 2026-11-11. That's 5 straight trading days (11-16 through 11-20) with no new
   target set, despite the strategy's own rule that a fifth of the rotation sleeve
   should rebalance every other day. `reports/today.md`, written by today's run, reads
   *"Outside trade window (market closed) -- refreshing snapshot only. next_close=
   2026-11-23T16:00:00-05:00"* — i.e. the invocation landed just after the 16:00 ET
   close and, by the bot's own rule (`bot.py`: trade only when the market is open and
   ≤360 minutes from close), did nothing but refresh prices. If this is the only
   invocation each day, it would explain the full week of inaction — worth having
   whoever owns the scheduler confirm the job is actually firing earlier in the trading
   day (mid-session, as it clearly was through 11-11), not just once right after the
   close.
2. **Holdings vs. targets have drifted further than price action alone explains.**
   Comparing current dollar values to the last computed targets (scaled to the
   2026-11-13 capital of $933.62): `XLP` is 26% light ($20.61 actual vs. $27.98 target),
   `XBI` 17% light, `SSO` 16% light, `DBC`/`XLB`/`XLF` each roughly 6-8% light, while
   `XLE` and `XLV` are slightly heavy. This is exactly what a week of unrebalanced
   drift during a down move looks like (names that fell hardest are now underweight
   their target), not a reconciliation bug — but it's a direct symptom of #1: the
   staggered-tranche mechanism that would normally correct this every other day hasn't
   run.
3. **Not halted.** No `halted` key in `signals/state.json`. Drawdown from the
   high-water mark ($1,029.15) to current equity ($882.76) is about -14.2%, still well
   below the 40% kill-switch threshold for `guarded_growth` (config.json's
   `executor.max_drawdown_halt: 0.3` restates the global default, so per `config.py`'s
   preset-override rule the preset's 0.40 applies, not 0.30).
4. **News layer flagged a real shock today, but the book can't act on it while
   stalled.** `signals/news_risk.json` (generated 2026-11-20T21:17:49Z) reports
   `market_risk: 2` — "serious market-wide shock" (AI/tech-led selloff, S&P/Dow in
   correction, hawkish Fed talk) — which per the strategy's effect table should scale
   risk assets ×0.75 for the day. `signals/alert.json` independently flags SPY -3.5%,
   QQQ -5.7%, and the SSO holding -7.1% today. No vetoes were issued. Because the
   decision step hasn't run since 11-13 (#1), this risk-2 override has nothing to apply
   itself to yet — it will only take effect once a decision cycle actually runs. This
   is the clearest cost of the stall: the one risk control designed for exactly this
   kind of day is currently idle.
5. **Wash sales**: still 22 loss-sale/rebuy pairs, unchanged from last week (no new
   trades to add any). Immaterial in this sim context.

## Bottom line

Nothing in the portfolio's composition looks wrong for a credit-stressed regime with a
leveraged core — the problem this week is that the book hasn't made a new decision in
five trading days while the market had a genuinely bad one. The equity drop
(-5.45% for the week, -14.0% drawdown from the high-water mark) is plausibly explained
by the broad selloff `alert.json` and `news_risk.json` both independently confirm, not
by a bug in the holdings themselves. But the system that's supposed to respond to
exactly this kind of day — rebalance the rotation sleeve, apply the credit/news
risk-scaling — has been idle since 2026-11-13, per `reports/today.md`'s own
"market closed" message on every recent run. Before next week's review, someone should
confirm the scheduled job is actually running during market hours (not just catching
the post-close snapshot window) and force a decision cycle if needed; until then, the
book's weights will keep drifting away from target as prices move.
