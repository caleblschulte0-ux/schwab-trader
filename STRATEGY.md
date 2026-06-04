# Trading Strategy & Risk Rules (the roadmap)

## Prime directive
Never end up down more than the cash put into trades. Guaranteed by **buy-only /
defined-risk**: we only ever BUY to open (stocks, and occasionally puts), and we
only SELL to *close* something we already own. Never short stock; never sell/write
options to open. Those are the only things that can lose more than you put in — banned.

## Day trading: buy AND sell
This is a day/swing strategy — we both enter and exit.
- **BUY to open** a stock at Schwab's live ask.
- **SELL to close** the position for a profit or a small loss. Selling a stock you
  already own is just closing your own long — it does NOT break the prime directive.
- Each position has a take-profit and stop-loss; the bot watches live price every
  run and sells to close when either is hit (or on a genuine thesis-break SELL).
  Targets are kept TIGHT (≈ +5–10% take-profit / −3–6% stop) so trades actually
  close intraday and recycle the capital — not wide swing targets that sit open for
  days. Positions may still be held overnight — no forced end-of-day flatten.

## Pace / cadence
- The AI brain scans hourly (the routine); the executor acts every 15 min. Moderate
  day/swing trading — quick in/out, not second-by-second scalping.

## Account & sizing
- Starting capital: **~$1,000 total**.
- **Max ~$150 per trade.** Fixed dollars, NOT a percentage of account value. With
  ~$1,000 that's roughly up to ~6 concurrent positions.
- Scale per-trade size up later as comfort/balance grows.

## What to trade
- Lean **smaller-cap / lower-priced** names (where the big % moves are), but a clean
  larger-cap setup is fair game — no hard price band; size everything to the $150 cap.
- Tech-leaning but open. Picks are driven by **the market**, via a wide funnel
  (FMP movers + web search), not the owner's opinions.

## Performance tracking (while in DRY-RUN / paper)
- Every pick is committed to the repo (`signals/orders.json` history) — a timestamped
  record of every entry the brain proposed.
- **End of day:** ask in chat ("how'd today's picks do?"). Pull the day's picks, look
  up how each stock actually moved, and compute the hypothetical P&L — what you'd have
  made/lost if live. The whole point of DRY-RUN: prove it on paper first.

## Hard guardrails (enforced in code, bot.py)
- Buy-to-open only; sell only to close a held position. No shorting, no selling
  options to open.
- Max ~$150 per trade; bot re-checks against the live entry price and trims qty.
- Always buys at Schwab's live ask (the brain's limit_price is only a reference).
- Freshness check; skip symbols already held, with an open buy, or bought in the
  last 60 min (no double-buys); place nothing if orders can't be read (fail-safe).

## Account notes
- Cash account: avoids the $25k Pattern Day Trader rule, BUT proceeds settle T+1 —
  can't instantly reuse the same dollars; buying with unsettled cash can cause
  good-faith violations. Keep day-trade volume modest on a cash account.
- Buying puts needs options approval — owner believes the account is approved.
