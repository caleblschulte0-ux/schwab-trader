# BRAIN.md — Instructions for the trading routine

> The Claude routine reads THIS file every run and follows it. To change how the
> bot thinks, edit this file — no need to touch the routine prompt in the UI.
> Also read `STRATEGY.md` for the risk rules; this file is the per-run playbook.

> ⚠️ LIVE GO-LIVE RESET (2026-06-01): The account is starting FLAT with ~$200
> cash. Ignore any prior paper positions mentioned in earlier latest.md runs
> (SOUN, SOFI, BBAI were paper only and were NOT bought). Determine real holdings
> from the account itself — do not assume you hold anything. Trade fresh.

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
- Still update `signals/positions.md` (below) so the open-positions view is current.

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
- SELL entries need only `{"symbol":"...","action":"SELL"}`.
- Nothing qualifies → `{"generated_utc":"...","orders":[]}`.

### B. `signals/latest.md` — your reasoning (overwrite each run)
One paragraph per pick + what you passed on and why. Include a UTC timestamp.

### C. `signals/positions.md` — the at-a-glance dashboard (overwrite each run)
A running view of every OPEN position. Format:
```
# Open Positions — updated <UTC timestamp>

| Symbol | Qty | Entry | Take-profit | Stop | Last seen | Unrealized $ | Note |
|--------|-----|-------|-------------|------|-----------|--------------|------|
| SOUN   | 7   | 9.10  | 10.40       | 8.25 | 9.40      | +2.10        | held 2d |

**Open positions:** N   **Est. cash deployed:** $X of ~$200   **Powder left:** $Y
```
If flat, write "No open positions."

### D. `reports/today.md` — end-of-day P&L (ONLY on the last run of the day)
On the final run near/after the close (~3:00 PM CDT / 20:00 UTC), also write a
daily report:
```
# Daily Report — <YYYY-MM-DD>

## Trades considered today
- BUY BBAI 12 @ 5.15 (target 5.75 / stop 4.70) — outcome: hit target / hit stop / closed flat / still open
...

## P&L
| Symbol | Action | Entry | Exit (or last) | Shares | P&L $ |
|--------|--------|-------|----------------|--------|-------|
| BBAI   | BUY    | 5.15  | 5.75           | 12     | +7.20 |

**Total P&L today: +$X.XX**
```
Determine each exit honestly from the day's real price action.

## Commit
Commit and push ALL written files (orders.json, latest.md, positions.md, and
reports/today.md when applicable) DIRECTLY to `main`. No new branch, no PR.
