# Analyst review — week of 2026-10-10

_Covers the sim/paper book as of the last run, 2026-10-09 23:13 UTC._

## What it holds, and why

Running the **guarded_growth** preset (leveraged core + SPY/QQQ candidates + the
credit-stress insurance signal, 40% kill switch), fully invested —
`regime.exposure = 1.0`, cash is $4.27 of $1,016.71.

- **Core, 50% (`QLD`)**: QQQ is currently the strongest of its SPY/QQQ candidates by
  3-6-12 month momentum and above its 150-day average, so the core sleeve holds it via
  the 2x fund (`QLD`), as `core_leveraged: true` dictates for this preset.
- **Momentum rotation, 50% split 8 ways**: `DBC, EEM, SMH, USO, XBI, XLE, XLK, XLV` —
  exactly the "hold the top 8" rule, inverse-volatility weighted. Oil/commodities
  (`XLE` + `USO` + `DBC` ≈ 18% combined) is the only real cluster, well under the 40%
  cap; no single name is close to the 35% position cap (largest is `XLV` at ~9.2%).
- **Mean-reversion sleeve**: empty (`mr_positions: {}`), consistent with the backtest,
  which also shows 0 MR round-trips over 18 years.
- **Credit-stress / risk-off signals**: both false, breadth 0.552 — nothing is being
  routed to `BIL`.
- **News layer**: reading risk level 0 today, no vetoes; no overrides scored yet (book
  is too new), so nothing to report there.

Position weights in `holdings.json` (equity $1,016.71) track the `targets.json` weights
closely — e.g. `QLD` 50.1% vs. 50.0% target, `XLV` 9.6% vs. 9.2% target — normal drift
from price moves since the last tranche touch, not a reconciliation problem. Holdings
and targets contain the identical 9 symbols; nothing extra, nothing missing.

## Live vs. backtest

Still early: the sim account is **17 calendar days old** (started 2026-09-22, only 14
equity points). `track_record.md` correctly flags CAGR as n/a (<30 days); the reported
Sharpe of 2.70 and the -1.8% max drawdown are small-sample artifacts, not numbers that
mean anything yet. Three closed round-trips so far (`QLD` x2, `XLE`), all winners — a
100% win rate off three trades isn't evidence of anything either way.

What *is* informative already: **execution quality**. Average fill cost across 15 fills
is +5.0 bps vs. the decision price, matching the backtest's assumed 5 bps slippage
almost exactly — a good sign the sim isn't quietly cheaper or more expensive to trade
than the model assumes. No wash sales detected.

For context, the strategy's own 18.7-year backtest for this exact preset/code path:
+13.1% CAGR, Sharpe 0.82, -22.0% max drawdown, beating SPY in every window tested with
less than half its drawdown. Nothing in the live equity curve so far ($1,000 →
$1,016.71) contradicts or confirms that — just too few data points.

## Anomalies

1. **No halt, no stall.** `signals/state.json` has no `halted` flag. The 2026-10-09 run
   that only refreshed the snapshot ("Outside trade window (market closed)") is expected,
   not stuck — markets were closed and the next session is 2026-10-12. This is a quiet
   weekend, not a stalled bot.
2. **High-water mark doesn't match the recorded equity curve.** `state.json` has
   `"hwm": 1029.15`, but the highest value anywhere in the 14-point equity curve
   (`paper_ledger.md` / `performance.json`) is $1,026.68 (2026-10-06) — about $2.47
   (0.24%) lower. The kill switch measures drawdown off the stored HWM, so it'd be worth
   a quick check on where that extra $2.47 came from (likely an intraday tick that never
   landed in the daily curve). Low stakes today — drawdown is only ~1.2–1.8% either way,
   nowhere near the 40% halt line — but the two numbers should agree.
3. **One trade below the configured minimum.** `config.json` sets
   `"min_trade_dollars": 5`, but `signals/executions.json` shows a 2026-10-01 `XLV` buy
   for a **$2.00** notional — below that floor. Every other trade in the log is $6+.
   Worth confirming whether small reconciliation top-ups are meant to bypass
   `min_trade_dollars`, or whether this one should've been skipped.
4. **Holdings vs. targets mismatch**: none — same 9 symbols, weights within normal
   tranche drift.
5. **Leverage note**: the core sleeve's use of a 2x fund (`QLD`) is by design — the
   "never leveraged" guardrail refers to margin, not the explicitly-permitted 2x index
   funds — but it does mean half the book carries double beta, the tradeoff the
   `aggressive`/`guarded_growth` presets are built around.

Nothing here looks broken. The book matches the rules on paper; items 2 and 3 are small
bookkeeping discrepancies worth a look, not red flags; otherwise it's simply too new to
judge against the backtest yet.
