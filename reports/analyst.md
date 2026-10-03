# Analyst review — week of 2026-10-02

_Covers the sim/paper book as of the last run, 2026-10-02 22:33 UTC._

## What it holds, and why

Running the **guarded_growth** preset (aggressive sleeve sizing + the credit-stress
insurance signal), fully invested — `regime.exposure = 1.0`, cash is $0.17.

- **Core, 50% (`QLD`)**: QQQ is currently the strongest of SPY/QQQ/EFA by 3-6-12 month
  momentum and above its 150-day average, so the core sleeve holds it via the 2x fund
  (`QLD`), as the aggressive-family presets do.
- **Momentum rotation, 50% split 8 ways**: `DBC, EEM, SMH, USO, XBI, XLE, XLK, XLV` —
  exactly the "hold the top 8" rule, inverse-volatility weighted. The only real cluster
  here is oil/commodities (`XLE` + `USO` + `DBC` ≈ 18% combined), well under the 40% cap;
  no single name is close to the 35% position cap.
- **Mean-reversion sleeve**: empty, consistent with the backtest, which also shows 0 MR
  round-trips over 18 years.
- **Credit-stress / risk-off signals**: both false, breadth 0.552 — nothing is being
  routed to `BIL`.
- **News layer**: no overrides scored yet (book is too new), so nothing to report there.

Position weights in `holdings.json` (equity $1,011.48) track the `targets.json` weights
within a few percent — e.g. QLD 50.0% vs. 50% target, XLV 9.4% vs. 9.4% target — normal
drift from price moves since the last tranche rebalance, not a reconciliation problem.
Holdings and targets contain the identical 9 symbols; nothing extra, nothing missing.

## Live vs. backtest

Still early: the sim account is ~10 calendar days old (started 2026-09-22). `track_record.md`
correctly flags CAGR as n/a (<30 days); the reported Sharpe of 3.56 and the -1.2% max
drawdown are small-sample artifacts, not numbers that mean anything yet. One closed
round-trip so far (`QLD`, +2.11%, held 8 days) — a 100% win rate off a single trade isn't
evidence of anything.

What *is* informative already: **execution quality**. Average fill cost across 12 fills is
+5.0 bps vs. the decision price, matching the backtest's assumed 5 bps slippage almost
exactly — a good sign the sim isn't quietly cheaper or more expensive to trade than the
model assumes. No wash sales detected.

For context, the strategy's own 18.7-year backtest for this exact preset/code path: +13.1%
CAGR, Sharpe 0.81, -22.0% max drawdown, beating SPY in every window tested with less than
half its drawdown. Nothing in the live equity curve so far ($1,000 → $1,011.48) contradicts
or confirms that — just too few data points.

## Anomalies checked

- **Halt state**: nothing in the reviewed files indicates a halt; `targets.json` shows
  `"rebalanced": true` for 2026-10-02 and the equity curve has an unbroken run of daily
  points through that date.
- **Stalled run**: last data point is 2026-10-02 (Friday); today's review date (2026-10-03)
  is a Monday, so the gap is the weekend, not a stall.
- **Holdings vs. targets mismatch**: none — same 9 symbols, weights within normal
  intraday/tranche drift.
- **Leverage note**: the core sleeve's use of a 2x fund (`QLD`) is by design — the
  "never leveraged" guardrail refers to margin, not the explicitly-permitted 2x index
  funds — but it does mean half the book carries double beta, the tradeoff the
  `aggressive`/`guarded_growth` presets are built around.

Nothing here looks broken. The book matches the rules on paper; it's simply too new to
judge against the backtest yet.
