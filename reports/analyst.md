# Analyst review — week of 2026-10-17

_Covers the sim/paper book as of the last close, 2026-10-16._

## What it holds, and why

Running the **guarded_growth** preset. The credit-stress signal (`HYG/IEF` below its
50-day average) is active, which halves the normal risk budget and routes the rest to
`BIL` — that's why T-bills are 56.9% of the book this week, well above the usual
defensive sliver.

- **Core (would be 50%, now ~25% after the halving): `QLD`.** QQQ is currently the
  strongest of SPY/QQQ/EFA by 3-6-12 month momentum and above its 150-day average, so
  the core sleeve holds it via the 2x fund, as this preset's leveraged-core rule dictates.
- **Momentum rotation (would be 50%, now ~18% after the halving), split 8 ways**:
  `DBC, EWJ, QQQ, SPY, USO, XLE, XLK, XLV` — exactly the "hold the top 8" rule,
  inverse-volatility weighted. No name is near the 35% cap or any cluster near the 40%
  cap.
- `SMH` and `XBI` broke their 150-day averages and were dropped today — expected: a
  trend-break exit fires in *any* tranche the day it happens, not just the one scheduled
  to rebalance. Only tranche 4/5 ran its scheduled full rebalance, adding `EWJ`, `QQQ`
  and `SPY` — also as designed (a fifth of the sleeve turns over every other day).
- Total risk exposure is 43.1% (core 25% + rotation 18%), matching `regime.exposure`;
  breadth (share of the universe above its own trend) is a middling 44.8%.

## Live vs. backtest

The 18.7-year backtest for this exact preset/code path shows +13.2% CAGR, a -22.0% max
drawdown, and losing months 40% of the time — a strategy that wins by losing less often
and less deeply, not by avoiding down months altogether. The live sim book is only about
4 weeks old (since 2026-09-22), so `track_record.md` correctly marks CAGR as n/a; right
now it's down -3.10% with a -5.6% max drawdown — well inside the backtest's normal range
of rough patches, not a contradiction of it. The 16 closed round-trips (56% win rate,
-0.82/trade expectancy, 0.29 profit factor) are too few to mean anything — the ledger
itself flags this as directional-only below ~30 trades. One encouraging signal:
execution cost averages +5.0 bps vs. the decision price, matching the backtest's assumed
5 bps slippage almost exactly, so the sim isn't quietly cheaper or pricier to trade than
the model assumes.

## Anomalies

1. **Holdings vs. targets mismatch — `EWJ` is missing.** `signals/targets.json` calls
   for a new `EWJ` stake (0.64% weight) from today's tranche-4 rebalance, alongside `QQQ`
   and `SPY`. `signals/holdings.json` shows `QQQ` and `SPY` were bought (small sub-1%
   stakes matching target), but there is no `EWJ` position at all — account cash is down
   to $0.12, leaving no room for it. Every other position's dollar value tracks its
   target weight closely, so this looks like one missed/skipped `EWJ` order rather than a
   broader sync problem. Worth checking the run log for an order rejection on `EWJ` for
   2026-10-16.
2. **No stall evident.** `paper_ledger.md` and `track_record.md` were both stamped
   2026-10-16 ~22:48–22:49 UTC, within a minute of each other; 2026-10-17 is a Saturday,
   so there is nothing new to run — a quiet weekend, not a stuck bot.
3. **No halt indicated by the data reviewed.** `signals/targets.json` shows
   `"rebalanced": true` and `regime.risk_off: false` for the latest run, i.e. the bot
   executed normally rather than sitting in a defensive halt. (`signals/state.json`,
   where the kill-switch flag actually lives, wasn't in scope for this review — worth a
   direct check if a halt is suspected.)
4. **One wash sale**: `QLD` sold at a loss on 2026-10-14 and repurchased on 2026-10-08
   (within 30 days). Immaterial here (sim/paper); in a taxable account it would only
   defer, not lose, the loss.
5. **News layer has nothing to score yet** — zero overrides logged, so there's no live
   evidence yet on whether it adds or costs value.

Nothing here looks structurally broken — the book matches the strategy's own rules.
Item 1 (the missing `EWJ` leg) is the one worth a follow-up; the rest is normal
small-sample noise this early in the paper run.
