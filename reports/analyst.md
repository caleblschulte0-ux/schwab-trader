# Analyst review — week of 2026-10-23

_Covers the sim/paper book as of the last close, 2026-10-23._

## What it holds, and why

Still the **guarded_growth** preset. The credit-stress signal (`HYG/IEF` below its
50-day average) remains active, halving the normal risk budget and routing the rest to
`BIL` — that's why T-bills are 53.1% of the book this week (`regime.exposure` = 0.469
risk-on, consistent with 53% defensive).

- **Core (would be 50%, now 25% after the halving): `QLD`.** QQQ is still the
  strongest of SPY/QQQ/EFA by 3-6-12 month momentum and above its 150-day average, so
  the core sleeve holds it via the 2x fund, as this preset's leveraged-core rule
  dictates.
- **Momentum rotation (would be 50%, now ~22% after the halving): 10 names** —
  `DBC, EWJ, QQQ, SPY, USO, XBI, XLE, XLK, XLP, XLV`. That's two more than the "hold the
  top 8" headline rule, but `signals/state.json` shows these are legacy holdings cycling
  through the 5-tranche, 10-day staggered schedule (tranches at day 1, 3, 5, 7, 9 of
  their cycle) and the strategy explicitly lets a name ride until it falls out of the
  top 11 — not a rule violation. `QQQ` appears in both the core and rotation sleeves at
  once, which STRATEGY.md allows ("the two slices add up"). No name is near the 35%
  per-ETF cap.
- Breadth (share of the universe above its own trend) is a middling 44.8%, basically
  unchanged from last week.

## Live vs. backtest

The 18.8-year backtest for this exact preset/code path shows +12.8% CAGR, a -22.0% max
drawdown, and losing months 40% of the time — a strategy that wins by losing less
often and less deeply, not by avoiding down months altogether. The live sim book is
about 4.5 weeks old (since 2026-09-22): it's now down **-3.30%** with a **-5.9%** max
drawdown from its $1,029.15 high-water mark — a second losing month in a row, but still
well inside the backtest's normal range of rough patches (40% of months lose there
too), not a contradiction of it. The 19 closed round-trips (47% win rate, -0.71/trade
expectancy, 0.28 profit factor) are still too few to read anything into — the ledger
itself flags this as directional-only below ~30 trades. One encouraging signal persists:
execution cost averages +5.0 bps vs. the decision price, matching the backtest's assumed
5 bps slippage almost exactly, so the sim isn't quietly cheaper or pricier to trade than
the model assumes.

## Anomalies

1. **Holdings vs. targets — several sleeve names are running under their target
   weight.** At the ~$968 book size implied by `signals/targets.json`, `XLP` should be
   about $8.09 but holds $4.24 (roughly half), and `EWJ` should be about $20.87 but
   holds $13.72 (about two-thirds). `QQQ` and `XLK` are modestly under too, while `DBC`
   and `USO` are a bit over. This lines up with the staggered-tranche design — each
   name's position size lags its newest target weight until its own tranche comes up
   for rebalance — rather than a sync bug; `BIL`, `QLD`, `SPY`, `XBI`, `XLE` and `XLV`
   all track their target weights closely. Worth a glance next week to confirm `XLP`
   and `EWJ` catch up on their next tranche rather than staying persistently
   underweight.
2. **`"rebalanced": false` in `targets.json` — not a stall.** It reflects the same
   staggered schedule: only one-fifth of the rotation sleeve turns over on any given
   day, and today wasn't that tranche's turn. `signals/state.json`'s run timestamps
   (`last_run_utc`, `last_decision_date`, `last_trade_date`, all 2026-10-23) line up
   exactly with `targets.json` and `holdings.json`, so nothing is stuck.
3. **Not halted.** `signals/state.json` has no `halted` key. High-water mark is
   $1,029.15 vs. current equity $966.96 — a 6.0% drawdown, nowhere near the
   `guarded_growth` 40% kill-switch threshold.
4. **Four wash sales now** (`QLD` twice, `XBI` twice) — up from one last week, a
   byproduct of the short, staggered rebalance cycle (median holding period 20 days).
   Immaterial in the sim/paper book; in a taxable account these would only defer, not
   lose, the loss — irrelevant in an IRA.
5. **News layer has nothing to score yet** — zero overrides logged, so there's still no
   live evidence on whether it adds or costs value.

Nothing here looks structurally broken — the book is doing what the strategy's own
rules say it should: credit-stress insurance has cut risk roughly in half, no run is
stuck or halted, and the target/holdings gaps trace to the intentional staggered
rebalance mechanism. The live paper track record is still too short to compare
meaningfully against the 18-year backtest; the one clean apples-to-apples read so far —
execution cost vs. the backtest's slippage assumption — continues to line up well.
