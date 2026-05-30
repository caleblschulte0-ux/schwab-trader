# Trading Strategy & Risk Rules (the roadmap)

## Prime directive
Never end up down more than the cash put into trades. Guaranteed by **buy-only /
defined-risk**: we only ever BUY (stocks, and occasionally puts). Never short
stock; never sell/write options. Those are the only things that can lose more
than you put in — banned.

## Account & sizing (start small)
- Starting capital: **~$200 total**.
- **Max ~$65 per trade** (so up to ~3 positions at once). Fixed dollars, NOT a
  percentage of account value — it won't balloon as the balance grows.
- Scale the per-trade size up later as comfort/balance grows.

## What to trade
- Mostly **lower-priced / smaller-cap stocks** (roughly $5–$20 while money's
  tight) — but **the bot picks**; no hard price band imposed by the owner.
- **Occasionally a put** (defined-risk downside bet) to test it.
- Tech-leaning but open. Picks are driven by **the market, not the owner's
  opinions** ("read what the market's saying").

## Style
- Mid-to-high risk. Day-trade / very short holds. Fast-ish in and out.

## How picks get made (free tiers)
- **Auto (GitHub bot, free):** signal-based — unusual volume, momentum /
  breakouts, sharp % moves — as a proxy for "something's about to happen."
- **Judgment (chat with the AI, free):** research a name on request and suggest
  a bet. True news/catalyst calls live here (or a paid API for fully autonomous).

## Hard guardrails (enforced in code)
- Buy-only. No short stock. No selling options.
- Max ~$65 per trade.
- Optional: cap on number of new trades per day.

## Account notes
- Cash account: avoids the $25k Pattern Day Trader rule, but cash must settle
  (options T+1), which limits same-day recycling of the same dollars.
- Buying puts needs options approval — owner believes the account is approved;
  verify the level allows buying puts.
