# Analyst review — week of 2026-10-31

_Covers the sim/paper book as of the last close, 2026-10-30._

## What it holds, and why

Still the **guarded_growth** preset. The credit-stress signal (`HYG/IEF` below its
50-day average) remains active, halving the normal risk budget and routing the rest to
`BIL` — that's why T-bills are 56.9% of the book this week (`regime.exposure` = 0.431
risk-on, consistent with 57% defensive).

- **Core (would be 50%, now 25% after the halving): `SSO`.** SPY is the strongest of
  SPY/QQQ/EFA by 3-6-12 month momentum and above its 150-day average, so the core
  sleeve holds it via the 2x fund, as this preset's leveraged-core rule dictates.
- **Momentum rotation (would be 50%, now ~17.5% after the halving): 7 of the 8
  target names** — `DBC, SPY, USO, XBI, XLE, XLP, XLV`. The commodity/defensive tilt
  (energy, materials, staples, healthcare, oil, broad commodities) instead of
  growth/tech is explained by this cycle's tranche log: `XLK`, `EWJ` and `QQQ` were
  dropped across three of the five tranches for breaking their 150-day average, and
  `XBI`, `XLP`, `XLB` were rotated in on the tranche-4 rebalance. No name is near the
  35% per-ETF cap.
- Breadth (share of the universe above its own trend) is 37.9%, weaker than last
  week's 44.8% — consistent with the credit-stress overlay staying on.

## Live vs. backtest

The 18.8-year backtest for this exact preset/code path shows +12.8% CAGR, a -22.0% max
drawdown, and losing months 40% of the time — a strategy that wins by losing less
often and less deeply, not by avoiding down months altogether. The live sim book is
about 5.5 weeks old (since 2026-09-22): it's now down **-4.60%**, equity $1,000 →
$954.00, with a **-7.1%** max drawdown — a third losing stretch in a row, but still
inside the backtest's normal range of rough patches. The "-36.4% CAGR" and "-2.75
Sharpe" in `track_record.md` are just this 5-week loss annualized, not a meaningful
rate over such a short window — don't read them as a verdict on the strategy.

The trade-level ledger is the weaker signal this week: 36 closed round-trips, 28% win
rate, profit factor 0.09, expectancy -1.58/trade — worse than prior weeks. Most of the
damage is tranche churn in a choppy month (`XLK`, `EWJ`, `QQQ`, `QLD`, `SMH` bought and
sold within days of each other as 150-day trend breaks fired, including a -$35.42 QLD
exit on 2026-10-30). Execution cost still averages +5.0 bps vs. the decision price,
matching the backtest's assumed 5 bps almost exactly, so this isn't a slippage or
fill-quality problem — it's the cost of whipsaw in a trendless stretch, same mechanism
the strategy document itself warns about.

## Anomalies

1. **Holdings vs. targets — `XLB` is missing entirely.** `signals/targets.json`
   assigns `XLB` a 0.78% weight (~$7.41 of $954 equity) as part of this cycle's
   8-name rotation list, but `signals/holdings.json` has no `XLB` position at all.
   Every other target — `BIL`, `SSO`, `SPY`, `USO`, `XBI`, `XLP`, `XLE`, `XLV`, `DBC` —
   is present and reconciles reasonably against its target weight (small gaps are
   explained by price moves since the last rebalance, e.g. `XLV` and `XLE` are up
   9-11% unrealized). A position this small not making it into holdings looks like an
   unfilled or skipped order rather than a strategy decision — worth checking the order
   log for a rejected or below-minimum-size `XLB` buy from the 2026-10-30 run.
2. **Not halted, not stalled.** The run dated 2026-10-30 is one day old, `rebalanced:
   true`, and tranches are actively rotating (five tranche notes logged for the day) —
   no sign the bot is stuck or has hit the kill switch. Drawdown (-7.1%) is nowhere
   near the 40% `guarded_growth` kill-switch threshold.
3. **Wash sales piling up, mostly on `QLD`.** 17 loss-sale/rebuy pairs within 30 days
   are now logged — up sharply from prior weeks — with `QLD` responsible for 6 of
   them, including the largest single loss (-$35.42 on 2026-10-30, rebought against an
   2026-10-08 lot). Immaterial in the sim/IRA context, but worth knowing in advance if
   this book is ever run in a taxable account: the tranche-driven churn will keep
   generating real wash-sale basis adjustments.
4. **News layer has nothing to score yet** — zero overrides logged, so there's still
   no live evidence on whether it adds or costs value. Normal at this stage; nowhere
   close to the ~20-override sample size needed to judge it.

## Bottom line

The portfolio is holding what the rules say it should, for the reasons the rules give
(momentum rotation out of tech/Japan into commodities/defensives, plus a
credit-stress-driven shift to cash). The live loss so far is small and inside
historical norms, but the trade-level stats have gotten worse this week and the `XLB`
gap between target and actual holdings should be checked — everything else reconciles
cleanly against the strategy's own rules.
