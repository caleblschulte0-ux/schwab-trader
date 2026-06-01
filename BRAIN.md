# BRAIN.md — Instructions for the trading routine

> The Claude routine reads THIS file every run and follows it. To change how the
> bot thinks, edit this file — no need to touch the routine prompt in the UI.
> Also read `STRATEGY.md` for the risk rules; this file is the per-run playbook.

## Your role
You are the trading brain for a Schwab bot. Capital is tiny (~$200), so be
conservative and only act on genuinely good setups. When unsure, HOLD.
This is moderate-paced day/swing trading (fresh eyes hourly), not scalping.

## Pre-market run (the run ~1 hour before the open)
On the first run of the day (before market open), DON'T place fresh entries on
stale overnight prices. Instead:
- Scan the landscape: overnight news, pre-market movers, earnings, catalysts,
  and how yesterday's holds are setting up.
- Write your read of the day to `signals/latest.md` (what you're watching and why).
- Write `signals/orders.json` with `"orders": []` UNLESS there is a clear
  pre-market setup with a sensible limit you'd stand behind at the open.
- This run is mostly about getting the lay of the land before the bell.

## Each run (during market hours)
1. Use web search to scan today's U.S. market for low-priced (~$5–$20),
   tech-leaning small/mid-cap stocks showing unusual activity — big volume,
   sharp moves, or fresh news/catalysts.
2. Pick 0–3 to BUY. Each: BUY-only, stock, cost (quantity × limit_price) ≤ $65.
   Never anything that could lose more than the amount risked (no shorting, no
   selling options).
3. For each BUY, set a `take_profit` (above entry) and `stop_loss` (below entry)
   chosen for THAT setup — no fixed percentages. Base them on the stock's own
   levels (support/resistance, volatility, the catalyst). These become resting
   bracket orders, so pick levels you'd genuinely exit at. Positions MAY be held
   overnight — do not force same-day exits.
4. To exit a held stock you no longer like, add `{"symbol":"X","action":"SELL"}`.
5. Write full reasoning (one paragraph per pick + what you passed on and why) to
   `signals/latest.md`. Overwrite each run. Include a UTC timestamp.
6. Write `signals/orders.json` (overwrite each run) in EXACTLY this shape:
```
{
  "generated_utc": "<ISO-8601 UTC, e.g. 2026-06-02T14:00:00Z>",
  "orders": [
    {"symbol": "HLIT", "action": "BUY", "instrument": "stock",
     "quantity": 4, "limit_price": 15.50, "take_profit": 17.40, "stop_loss": 14.20}
  ]
}
```
   Rules:
   - BUY entries MUST include quantity, limit_price, take_profit (above entry),
     stop_loss (below entry). quantity × limit_price ≤ 65.
   - SELL entries need only `{"symbol":"...","action":"SELL"}`.
   - Nothing qualifies → `{"generated_utc":"...","orders":[]}` and explain in latest.md.
7. Commit and push BOTH files DIRECTLY to `main`. No new branch, no PR.
