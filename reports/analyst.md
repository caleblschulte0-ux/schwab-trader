# Analyst review — week of 2026-09-26

_Covers the sim/paper book as of the last run, 2026-09-25 21:32 UTC._

## What it holds, and why

Running the **guarded_growth** preset (aggressive sleeve sizing + the credit-stress
insurance signal), fully invested — no cash sitting idle beyond $2.01 in change.

- **Core, 50% (`QLD`)**: QQQ is currently the strongest of SPY/QQQ/EFA by 3-6-12 month
  momentum and above its 150-day average, so the core sleeve holds it via the 2x fund
  (`QLD`) as the aggressive-family presets do. `regime.exposure = 1.0` confirms nothing is
  being defensively trimmed.
- **Momentum rotation, 50% split 8 ways**: `DBC, EEM, SMH, USO, XBI, XLE, XLK, XLV` —
  each has a positive momentum score and trades above its own 150-day average, weighted
  inverse-volatility per the rules. That's exactly 8 names, matching the "hold the top 8"
  rule. No sector cluster is close to the 40% cap (the oil/commodities trio XLE+USO+DBC,
  the closest thing to a cluster here, is ~18.6% combined).
- **Mean-reversion sleeve**: empty, same as the backtest, which also shows 0 MR
  round-trips over 18 years — consistent, not a bug.
- **Credit-stress / risk-off signals**: both false. `breadth = 0.586`. Nothing is being
  routed to `BIL`.
- **News layer**: risk level 0 today, no vetoes. The model read today's dominant
  storylines (10-year yield near 19-year highs, hawkish Fed ahead of midterms, an
  Iran/Hormuz oil standoff that's currently pushing crude *down* on diplomacy hopes) and
  correctly judged none of it a fresh, fund-specific shock — old news, already priced.

Actual position weights (from `holdings.json`, equity $1,005.02) track the `targets.json`
weights within a point or so — e.g. QLD 50.4% vs. 50% target, XBI 5.9% vs. 5.7% — which is
just normal drift from price moves since the last full rebalance on 2026-09-24, not a
reconciliation problem. Holdings and targets contain the identical 9 symbols.

## Live vs. backtest

Too early to say much: the sim account is 3 trading days old (started 2026-09-22, first
trades filled 2026-09-24). `track_record.md` correctly flags CAGR as n/a (<30 days); the
reported Sharpe of 16.9 is a small-sample artifact, not a real number yet.

What *is* informative already: **execution quality**. Average fill cost is +5.0 bps vs.
the decision price across all 9 opening trades — matching the backtest's assumed 5 bps
slippage almost exactly. That's a good early sign the sim isn't quietly cheaper or more
expensive to trade than the model assumes. No closed round-trips and no wash sales yet,
as expected this early.

For context, the strategy's own 18-year backtest for this exact preset/code path: +13.2%
CAGR, -22% max drawdown, beats SPY in every window tested with less than half its
drawdown. Nothing in the 4-point live equity curve ($1,000 → $1,005.02) contradicts or
confirms that yet — just too few data points.

## Anomalies checked

- **Halt state**: `signals/state.json` has no `halted` key — not halted. High-water mark
  ($1,004.64) sits just under current equity; nowhere near the 40% guarded_growth kill
  switch.
- **Stalled run**: last run was 2026-09-25 21:31 UTC, one day before this review
  (2026-09-26). That's a normal daily cadence, not a stall — today's run just hasn't
  landed yet at review time.
- **Holdings vs. targets mismatch**: none found — same 9 symbols, weights within normal
  daily drift.
- **Leverage note**: the core sleeve uses a 2x fund (`QLD`), which is allowed by design
  (the "never leveraged" rule refers to margin, not the explicitly-permitted 2x index
  funds) — worth remembering that this doubles the effective beta of half the book, which
  is the tradeoff `guarded_growth`/`aggressive` are built around.

Nothing here looks broken. The book matches the rules on paper; it's simply too new to
judge against the backtest yet.
