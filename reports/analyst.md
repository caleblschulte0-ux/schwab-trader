# Analyst review — week of 2026-11-28

_Covers the sim/paper book through the last close, 2026-11-27. Top finding: the trading
decision loop is still stalled since 2026-11-13 — now two full weeks — see "Anomalies
checked" #1. This is a repeat of last week's top finding; it has not been fixed._

## What it holds, and why

Still **guarded_growth**, and still the same positions as last week, because — as
before — nothing has actually traded:

- **~54% in BIL (T-bills)** ($493.25 of $913.63 equity). The **credit-stress signal**
  (`HYG/IEF` below their 50-day average) was active as of the last computed regime
  (`regime.credit_stress: true`, `regime.exposure: 0.475`), which halves the risk budget
  for both sleeves per `STRATEGY.md`. This is the strategy working as designed, not a new
  decision — the weight has just drifted slightly as the risk sleeve's dollar value moved
  against a flat BIL.
- **~24% core, in SSO** ($218.06). The leveraged S&P proxy was the strongest of
  SPY/QQQ/EFA as of the last computed cycle (2026-11-13) and sits above its 150-day
  average; it's held at half its normal 50% weight because of the credit-stress halving.
  SSO is down -6.2% since its 2026-11-10 entry, in line with the market's late-November
  wobble.
- **~22% momentum rotation, the same 8 names as two weeks ago**: `DBC, USO, XBI, XLB,
  XLE, XLF, XLP, XLV` — energy, materials, financials, staples, healthcare/biotech and
  two commodity funds. These are still the targets computed on 2026-11-13
  (`signals/targets.json`); no newer target set exists, so this allocation is now two
  weeks stale.
- Mean-reversion sleeve remains empty, matching the 18-year backtest (0 round-trips) —
  expected, not a flag.

## Live vs. backtest

`reports/backtest.md` (18.9 years, same preset/code path) shows +12.4% CAGR, Sharpe
0.78, a -22.0% max drawdown, and losing months 40% of the time. The live sim book is now
~9.4 weeks old (since 2026-09-22): equity has gone $1,000 → $913.63, **-8.64% total**,
with a **-14.0%** max drawdown (`track_record.md`). That's an improvement from last
week's -11.72%/$882.76 read — the book recovered about $31 (+3.5%) over the past week as
markets bounced (see news layer, below). The reported -39.3% "CAGR" / -2.98 "Sharpe" are
this ~9-week stretch annualized and still too short a sample to be meaningful on their
own, but the trend this week is a partial recovery, not further deterioration.

Trade-level stats are **unchanged from two weeks ago**: 44 closed round-trips, 27% win
rate, profit factor 0.08, expectancy -1.57/trade, 76 fills, $3,980 traded, average cost
+5.0 bps, 22 wash-sale pairs. Unchanged because, per the stall below, zero trades have
opened or closed since 2026-11-11.

## Anomalies checked

1. **The decision loop is still stalled — now two weeks, not one.** `signals/state.json`
   shows `last_decision_date` and `last_trade_date` both still stuck at `2026-11-13`,
   while `last_seen_date`/`last_run_utc` (2026-11-27T21:55:59Z) confirm the job keeps
   firing daily. `signals/targets.json` still carries the 2026-11-13 date. No fill in
   `signals/executions.json` is newer than 2026-11-11. `reports/today.md`, written by
   today's run, reads *"Outside trade window (market closed) -- refreshing snapshot
   only. next_close=2026-11-30T16:00:00-05:00"* — the same root cause flagged last week:
   the scheduled invocation is landing after the close, and `bot.py` only trades when
   the market is open and within 360 minutes of the close, so every recent run does
   nothing but mark prices. This has now persisted for 10 straight trading sessions
   (11-16 through 11-27) without a fix. This should be escalated rather than re-flagged
   a third time next week — whoever owns the scheduler needs to move the invocation
   into market hours.
2. **Holdings vs. targets: consistent with price drift, not a reconciliation bug.**
   Scaling the 2026-11-13 targets to the current $913.63 equity, today's dollar weights
   track the stale targets closely — the small gaps that exist (BIL slightly heavy,
   XBI/USO slightly light) are exactly what two weeks of unrebalanced price movement
   would produce. This is a symptom of #1, not a separate problem.
3. **Not halted.** No `halted` key in `signals/state.json`. Drawdown from the
   high-water mark ($1,029.15) to current equity ($913.63) is about -11.2%, well below
   the 40% kill-switch threshold for `guarded_growth`.
4. **News/alert risk has eased since last week.** `signals/news_risk.json` (generated
   2026-11-27T21:55:46Z) now reads `market_risk: 1` ("elevated," logged only) — down
   from last week's level 2 "serious market-wide shock" — citing a rebound after the
   November tech rout, still-high long yields, new tariffs, and Fed/geopolitical
   headlines, with no vetoes issued. `signals/alert.json` (dated 2026-11-20, not
   refreshed since) still shows the prior week's selloff flags. Because the decision
   step hasn't run since 11-13, neither the risk-1 reading nor the earlier risk-2
   override have had anything to apply themselves to — the risk-scaling control
   remains idle regardless of what the news layer reports.
5. **Wash sales**: still 22 loss-sale/rebuy pairs, unchanged (no new trades to add any).
   Immaterial in this sim context.

## Bottom line

Composition still looks correct for a credit-stressed regime with a leveraged core, and
the book actually recovered a bit this week as markets calmed. The real story is
unchanged from last week: the decision loop has not produced a new target set in two
weeks because the scheduled run keeps landing outside the trade window, per
`reports/today.md`'s recurring "market closed" message. The rotation sleeve's staggered
tranches, the credit-stress halving, and the news-risk override are all designed to
react within days — none of them can do that while the job only ever catches the
post-close snapshot. This needs a scheduler fix, not another week of monitoring.
