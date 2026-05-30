# Trading Strategy & Risk Rules (the roadmap)

## Prime directive
Never end up down more than the cash put into trades. Guaranteed by **buy-only /
defined-risk**: we only ever BUY to open (stocks, and occasionally puts), and we
only SELL to *close* something we already own. Never short stock; never sell/write
options to open. Those are the only things that can lose more than you put in — banned.

## Day trading: buy AND sell
This is a day-trading strategy — we both enter and exit, often the same day.
- **BUY to open** a stock (or occasionally a put).
- **SELL to close** the position for a profit or a small loss. Selling a stock you
  already own is just closing your own long — it does NOT break the prime directive
  (you can't lose more than you put in by selling something you hold).
- Every entry rides with a **bracket**: an auto take-profit and an auto stop-loss,
  so each position exits itself. Optionally flatten any still-open day-trade
  positions before the close so nothing carries overnight.

## Pace / cadence (moderate, not hyper-aggressive)
- The AI brain gets fresh eyes on the market **once an hour** (the routine), and the
  executor acts **every 30 min**. So this is **moderate-speed** day trading — quick
  in/out, but not second-by-second scalping. That's intentional while the account is
  small; we can tighten later.

## Account & sizing (start small)
- Starting capital: **~$200 total**.
- **Max ~$65 per trade.** Fixed dollars, NOT a percentage of account value.
- Scale per-trade size up later as comfort/balance grows.

## What to trade
- Mostly **lower-priced / smaller-cap stocks** (roughly $5–$20 while money's tight)
  — but **the bot picks**; no hard price band imposed by the owner.
- **Occasionally a put** (defined-risk downside bet).
- Tech-leaning but open. Picks are driven by **the market, not the owner's opinions**.

## Performance tracking (while in DRY-RUN / paper)
- Every hourly pick is committed to the repo (`signals/orders.json` history) — a
  timestamped record of every entry the brain proposed.
- **End of day:** the owner asks in chat ("how'd today's picks do?"). The assistant
  reads the day's picks from the repo history, looks up how each stock actually moved
  that day, and computes the hypothetical P&L — i.e. "what you would have made/lost
  if it were live." This is the whole point of DRY-RUN: prove it on paper first.

## Hard guardrails (enforced in code)
- Buy-to-open only; sell only to close a held position. No shorting, no selling
  options to open.
- Max ~$65 per trade.
- Freshness check (don't act on stale picks) + skip symbols already held.
- (Before going live) add open-order de-dup so a pick isn't ordered twice.

## Account notes
- Cash account: avoids the $25k Pattern Day Trader rule, BUT sale proceeds settle
  T+1 — you can't instantly reuse the same dollars, and buying with unsettled cash
  can cause good-faith violations. Keep day-trade volume modest on a cash account.
- Buying puts needs options approval — owner believes the account is approved.
