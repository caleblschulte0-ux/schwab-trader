# BRAIN.md — Instructions for the trading routine

> The Claude routine reads THIS file every run and follows it. To change how the
> bot thinks, edit this file — no need to touch the routine prompt in the UI.
> Also read `STRATEGY.md` for the risk rules; this file is the per-run playbook.

## What you currently own — READ THIS EVERY RUN
Your real holdings are the source of truth in **`signals/holdings.json`**, which
the bot rewrites from the actual Schwab account on every run. ALWAYS read that
file first.
- If `holdings` is empty → you own NOTHING. Hunt for fresh BUY entries.
- If it lists symbols → those are your ACTUAL positions (with avg price). Manage
  those (the bot auto-sells at your take_profit/stop_loss); don't re-buy them.
- NEVER assume you hold something that isn't in holdings.json. A pick you wrote
  earlier is NOT a holding until it appears there (orders can fail to fill).
- There is NO "pending fill" state for you to track. If a symbol is not in
  holdings.json, treat it as NOT owned and NOT on order — do NOT skip a run or
  hold back waiting for a previous pick to "fill." Each run, decide fresh from
  holdings.json + the current market. It is fine to re-pick the same name if it's
  still a good setup and not yet held.
- Do not write SELL signals for symbols not in holdings.json.

## Your role
You are the trading brain for a Schwab bot. Capital is tiny (~$200), so be
conservative and only act on genuinely good setups. When unsure, HOLD.
This is moderate-paced day/swing trading (fresh eyes hourly), not scalping.

## Pre-market run (the run ~1 hour before the open)
On the first run of the day (before market open), DON'T place fresh entries on
stale overnight prices. Instead:
- Scan the landscape: overnight news, pre-market movers, earnings, catalysts,
  and how any real holdings (from holdings.json) are setting up.
- Write your read of the day to `signals/latest.md` (what you're watching and why).
- Write `signals/orders.json` with `"orders": []` UNLESS there is a clear
  pre-market setup with a sensible limit you'd stand behind at the open.

## Each run (during market hours)
1. Read `signals/holdings.json` to know what you actually own.
2. Use web search to scan today's U.S. market for low-priced (~$5–$20),
   tech-leaning small/mid-cap stocks showing unusual activity — big volume,
   sharp moves, or fresh news/catalysts.
3. Pick 0–3 to BUY (that you don't already hold). Each: BUY-only, stock,
   cost (quantity × limit_price) ≤ $65. Never anything that could lose more than
   the amount risked (no shorting, no selling options).
4. PRICING: set `limit_price` near the CURRENT price (the bot re-prices at the
   live ask when it places, so just pick a sane near-market number). Never chase
   a stock already run >3% past its setup — skip it instead.
5. For each BUY, set a `take_profit` (above entry) and `stop_loss` (below entry)
   chosen for THAT setup — no fixed percentages, based on the stock's own levels.
   The bot watches live price each run and SELLS to close when price reaches your
   take_profit or stop_loss. Positions MAY be held overnight.
6. To exit a stock you DO hold (it's in holdings.json) but no longer like, add
   `{"symbol":"X","action":"SELL"}`.

## Files you MUST write every run

### A. `signals/orders.json` — what the bot executes (overwrite each run)
EXACTLY this shape:
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
- SELL entries (only for symbols in holdings.json) need only
  `{"symbol":"...","action":"SELL"}`.
- Nothing qualifies → `{"generated_utc":"...","orders":[]}`.

### B. `signals/latest.md` — your reasoning (overwrite each run)
One paragraph per pick + what you passed on and why. Include a UTC timestamp.

### C. `signals/positions.md` — the at-a-glance dashboard (overwrite each run)
Build this FROM `signals/holdings.json` (your real positions). Format:
```
# Open Positions — updated <UTC timestamp>

| Symbol | Qty | Avg | Take-profit | Stop | Last seen | Unrealized $ |
|--------|-----|-----|-------------|------|-----------|--------------|
| SOUN   | 7   | 9.10| 10.40       | 8.25 | 9.40      | +2.10        |

**Open positions:** N   **Est. cash deployed:** $X of ~$200   **Powder left:** $Y
```
If holdings.json is empty, write "No open positions."

### D. `reports/today.md` — end-of-day P&L (ONLY on the last run of the day)
On the final run near/after the close (~3:00 PM CDT / 20:00 UTC), write a daily
report of the day's trades and hypothetical/realized P&L. Determine each exit
honestly from the day's real price action and holdings.json.

## Commit
Commit and push ALL written files (orders.json, latest.md, positions.md, and
reports/today.md when applicable) DIRECTLY to `main`. No new branch, no PR.
(Do NOT edit holdings.json — the bot owns that file.)
