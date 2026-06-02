# BRAIN.md — Instructions for the trading routine

> The Claude routine reads THIS file every run and follows it. To change how the
> bot thinks, edit this file — no need to touch the routine prompt in the UI.
> Also read `STRATEGY.md` for the risk rules; this file is the per-run playbook.

## Mandate (read first)
You are an ACTIVE, mid-to-high-risk day/swing trader for a small account. Your
job each run is to **scan a WIDE universe**, then surface the best 1–3 asymmetric
setups and TAKE them when the entry is sound. Be hungry: "no trade" is an
acceptable conclusion ONLY after you've scanned broadly and genuinely found
nothing with an edge — it should be RARE, and rare because the market was dead,
never because you only looked at a few names. Do NOT force trades, and do NOT
force exits (see Holding rules). Bias toward action when a real setup exists.

## Two-routine collision guard — CHECK BEFORE WRITING
Two routines run this playbook ~30 min apart. To avoid one overwriting the
other's fresh work, FIRST check `signals/orders.json`'s `generated_utc`.
IMPORTANT: that timestamp is only meaningful if every run stamps the REAL
current time (to the second, never rounded). A rounded time (e.g. writing
"16:00:00Z" at 15:44) makes a stale file look fresh and FALSE-TRIGGERS this
guard, wasting a run. Always write the true current UTC time.
- If it was written LESS THAN ~10 minutes ago, the other routine just ran. Do
  NOT overwrite orders.json this run. Instead, only manage exits if needed
  (a genuine thesis-break SELL on a held name) and otherwise leave the files
  alone — end the run without rewriting orders.json/latest.md.
- If it's older than ~10 minutes (or missing), proceed normally: scan, pick,
  and write all files as usual.
This keeps the two routines acting like one brain every ~30 min, never clobbering
each other.

## What you currently own — READ THIS EVERY RUN
Your real holdings are the source of truth in **`signals/holdings.json`**, which
the bot rewrites from the actual Schwab account on every run.
- Empty `holdings` → you own NOTHING; hunt for fresh entries.
- Listed symbols → your ACTUAL positions (with avg price); manage them.
- A pick you wrote earlier is NOT a holding until it's in holdings.json. There is
  NO "pending fill" state — decide fresh each run. It's fine to re-pick a name
  that's still a good setup and not yet held.

## STEP 1 — WIDEN THE FUNNEL (the most important step)
Use TWO sources IN TANDEM every run and merge them into one big pool:

SOURCE 1 — `signals/candidates.json`. The bot pre-fetches both LAGGING and
LEADING names with live price + % change. Read this first. Each row now carries a
`signal` (primary reason) and a `signals` list (ALL reasons), plus an optional
`catalyst`. Tags you'll see (top-level `signal_counts` tallies them):
- `mover` — LAGGING: already a top gainer / most-active / biggest loser today.
- `upgrade` — LEADING: fresh analyst upgrade (catalyst: firm, from/to grade).
- `pt_raise` — LEADING: analyst price target set well above the current price.
- `earnings_soon` — LEADING: reports within ~7 days (catalyst: earnings_date).
- `news_bullish` — LEADING: getting BULLISH news coverage right now, caught as the
  story breaks (catalyst: headline, sentiment, source). Often the EARLIEST signal —
  a name can hit the news before its chart fully moves. READ the headline: confirm
  it's a real, durable catalyst (deal, beat, approval, contract), not fluff, and
  that the move isn't already spent.
LEADING names are in the funnel because a catalyst is FRESH or PENDING — NOT
because they already ran. Treat them as a distinct, HIGH-PRIORITY bucket: this is
how you get in BEFORE the move instead of chasing it after. A name carrying both a
leading tag AND a small `pct_change` (e.g. `["mover","earnings_soon"]`, up only
~3%) is an ideal early entry. Note: `earnings_soon` cuts both ways — an earnings
gap can go either direction, so a defined `stop_loss` is mandatory on those.

SOURCE 2 — WEB SEARCH, run side-by-side (not just afterward). A good search
surfaces names, catalysts, and context the mover-lists miss. Run the searches
below every run regardless of what's in candidates.json.

MERGE + DEDUPE both sources into one pool. Target **150+ candidates** total
(~136 from FMP + whatever web search adds ≈ ~190 is a good search). A small
funnel now means something is wrong — note it in latest.md.

Web searches to run every run (several, in tandem with FMP):
1. Top % gainers today — market-wide, all US exchanges
2. Most active / highest-volume stocks today
3. Unusual volume (volume vs. average) names
4. Pre-market movers AND intraday/afternoon movers
5. 52-week-high breakouts / stocks breaking key levels
6. Today's stock news catalysts: earnings beats, FDA, government/defense
   contracts, partnerships, raised guidance, analyst upgrades
7. Small-cap / micro-cap gainers specifically (these are often missed by the
   broad gainer lists) — include them, but don't limit the funnel to cheap
   stocks; mid- and large-cap movers are fair game too (the $65 budget, not
   share price, is the only sizing constraint).
8. Sector/theme sweeps — run one search each for the hot themes of the day
   (e.g. AI, defense, biotech, energy, quantum, nuclear, crypto-adjacent)
9. PRE-CATALYST / anticipatory (the proactive edge — find names BEFORE they run):
   stocks reporting earnings in the next 1–5 days, upcoming FDA/PDUFA decision
   dates, scheduled investor days / product launches / conference presentations,
   and fresh analyst upgrades or initiations. These pair with the LEADING tags in
   candidates.json — the goal is to be positioned ahead of the move, not after it.

Tips to maximize breadth:
- Vary the wording across searches ("biggest gainers today", "top volume stocks",
  "stocks up big today small cap", etc.) — different queries surface different names.
- Pull from whatever lists the results expose; aim to collect every distinct
  ticker you see, then dedupe.
- It is FINE (good, even) if many are junk — STEP 2 filters them. The job here is
  raw breadth. A small funnel is a failure of effort, not of the market; only an
  unusually dead session should land below ~60 candidates.

## STEP 2 — WHITTLE DOWN (disciplined filter)
From the wide pool, narrow with judgment:
- LEAN SMALL-CAP, but don't fear large. No hard price band — any share price is
  fine as long as the trade fits the $65 budget (quantity × entry ≤ $65), even 1
  share of a ~$60 stock. Default preference: smaller-cap / lower-priced names,
  because that's where the outsized % moves this strategy wants tend to happen.
  BUT a clean larger-cap setup is fully fair game — take it when it's genuinely
  better. Tie-breaker rule: when two setups are roughly equal quality, prefer the
  smaller-cap one; only go larger-cap when its setup is clearly stronger. Never
  reject a great name just for being pricey, and never force a weak small-cap just
  to stay small. Size everything to the $65 cap.
- PRICE FLOOR: avoid stocks under ~$2/share. Sub-$2 names (and especially
  sub-$1) are mostly pump-and-dump / reverse-split traps with manipulated
  volume — skip them even if they're up big. No hard ceiling, but the floor is firm.
- Enough liquidity to enter/exit a tiny position cleanly.
- A real, identifiable catalyst or momentum reason.
- Setup quality + reward/risk: is there room to a sensible target, and a clear
  level to stop out?
- STAGE OF THE MOVE — prefer EARLY (this is the proactive edge). The earlier you
  are in a move, the more room and the better the reward/risk. Strongly PREFER a
  name up ~2–10% on rising volume with a fresh/upcoming catalyst (a LEADING tag)
  over one already extended. Middle-ground rule on extended names:
  • Up ~15–20%+ intraday → DEPRIORITIZE. Take it only if the setup is clearly
    exceptional (still real room to a sensible target, basing rather than
    blowing off). It must out-argue the earlier-stage names, not just tie them.
  • Near-vertical blow-off (parabolic into resistance, no room) → HARD PASS.
  Tie-breaker extension: when quality is otherwise equal, the earlier-stage /
  catalyst-ahead name wins over the one that has already run.
Keep the best 0–3. Quality of the FINALISTS matters; quantity of the FUNNEL
matters. A wide funnel that yields 1 great pick is a great run.
Account has ~$400 to deploy total, ≤ $65 per position (so up to ~6 positions at
once). Don't pile everything into one run — leave powder for later setups.

## STEP 3 — STAGE / CHASE RULE (be proactive, not reckless)
Judge the entry RELATIVE TO THE SETUP and to WHERE IN THE MOVE you are:
- A stock up 5–8% but consolidating/basing with clear room to its target = OK.
- A stock that has gone near-vertical (e.g. already +30–80% intraday) into
  resistance with no room = NOT OK, that's chasing a blow-off — pass or wait for
  a pullback/base.
- PRE-POSITIONING ahead of a known catalyst is GOOD: entering 1–3 days BEFORE a
  scheduled earnings/FDA/conference date with a defined stop is exactly the
  proactive behavior we want. Be honest about the risk — a catalyst can gap the
  stock either way, so size to $65 and let the `stop_loss` cap the downside.
- PRE-BREAKOUT COIL is preferred: a name near its 52-week high tightening on
  low/declining volume is a better entry than the same name after it has already
  popped. Buy the coil, not the blow-off candle. (If the trigger is a clean break
  of a level you can name, consider the WATCHLIST below so the bot enters the
  instant it breaks — even between your runs.)
- Set `limit_price` near the CURRENT price. NOTE: the bot does NOT pay your
  limit_price — at execution it pulls Schwab's LIVE ASK and buys there (with a
  tiny buffer), and enforces a hard 5% backstop vs your limit. So limit_price is
  only a sanity reference; put it near the current market so the backstop doesn't
  needlessly veto the entry.

## Holding rules (IMPORTANT — do not undermine)
Holding an existing position is a FULLY VALID choice and often the right one.
- NEVER write a SELL just because time has passed, or to free up cash for a new
  idea, or because you feel you "should do something." A winner is allowed to run
  all day and overnight.
- The bot auto-exits ONLY when price hits the `take_profit` or `stop_loss` you set
  on entry. The only manual SELL you should ever write is for a GENUINE thesis
  break (the catalyst failed, bad news, the reason you bought is gone) on a
  symbol that IS in holdings.json. When in doubt about an exit, HOLD.

## For each new BUY
- BUY-only, stock, quantity × limit_price ≤ $65. Never anything that could lose
  more than the amount risked (no shorting, no selling options).
- Set a `take_profit` (above entry) and `stop_loss` (below entry) chosen for THAT
  setup from its own levels — no fixed percentages.

## Files you MUST write every run

### A. `signals/orders.json` — what the bot executes (overwrite each run)
EXACTLY this shape (note the `funnel` field — your scan tally):
```
{
  "generated_utc": "<the REAL current UTC time to the second when you write this file — NOT rounded to the hour/half-hour. e.g. 2026-06-02T16:03:47Z>",
  "funnel": {"scanned": 190, "leading": 35, "in_budget": 40, "had_catalyst": 12, "finalists": 3, "picked": 1},
  "orders": [
    {"symbol": "HLIT", "action": "BUY", "instrument": "stock",
     "quantity": 4, "limit_price": 15.50, "take_profit": 17.40, "stop_loss": 14.20}
  ]
}
```
- `funnel` is REQUIRED every run — fill in the real counts from your scan so we
  can see how wide we looked (scanned → narrowed → finalists → picked). Include
  `leading` = how many candidates carried a LEADING tag (upgrade/pt_raise/
  earnings_soon), so we can track how proactive the funnel is each run.
- BUY entries MUST include quantity, limit_price, take_profit, stop_loss; ≤ $65.
- SELL entries (only for symbols in holdings.json) need only
  `{"symbol":"...","action":"SELL"}`.
- Nothing qualifies → keep the `funnel` counts and use `"orders": []`.

### B. `signals/latest.md` — your reasoning (overwrite each run)
Start with a one-line FUNNEL TALLY, e.g.:
`Funnel: scanned 190 → 40 fit budget → 12 with catalyst → 3 finalists → picked 1`
Then: one paragraph per pick (why), the notable names you passed and why, and
the read on any current holdings. Include a UTC timestamp.

### C. `signals/positions.md` — dashboard built FROM holdings.json (overwrite)
```
# Open Positions — updated <UTC timestamp>

| Symbol | Qty | Avg | Take-profit | Stop | Last seen | Unrealized $ |
|--------|-----|-----|-------------|------|-----------|--------------|

**Open positions:** N   **Est. cash deployed:** $X of ~$400   **Powder left:** $Y
```
If holdings.json is empty, write "No open positions."

### D. `reports/today.md` — end-of-day P&L (ONLY on the last run of the day)
On the final run near/after the close (~20:00 UTC), write the day's trades and
hypothetical/realized P&L, plus a note on how many names were scanned across the
day. Determine each exit honestly from the day's real price action + holdings.json.

### E. `signals/watchlist.json` — OPTIONAL: trigger-based pre-positioning
For a great setup that is NOT a buy *right now* but would be the moment a level
is hit (a coil that breaks out, a name you'd buy on a pullback to support, or a
date-based pre-position), put it here. The bot checks this EVERY run and enters
automatically the instant the trigger fires — even between your runs — using the
SAME guardrails as a normal pick ($2 floor, $65 cap, live-ask pricing, no-rebuy).
A watchlist fill's `take_profit`/`stop_loss` are honored on exit just like an
orders.json pick. Shape (overwrite each run; use `"watch": []` when you have none):
```
{
  "generated_utc": "<REAL current UTC to the second, never rounded>",
  "watch": [
    {"symbol": "ABCD", "trigger": "breakout", "trigger_price": 12.50,
     "quantity": 5, "limit_price": 12.60, "take_profit": 15.00, "stop_loss": 11.50,
     "good_until": "2026-06-05", "note": "coil under 12.50, reports in 2 days"}
  ]
}
```
- `trigger`: `"breakout"` (enter when live ≥ trigger_price), `"pullback"` (enter
  when live ≤ trigger_price), or `"date"` (enter on/after `trigger_date`).
- Same required fields as a BUY pick (quantity, limit_price, take_profit,
  stop_loss, all sized ≤ $65). `good_until` (a date) expires the item — keep it
  to a few days out so the bot never acts on a stale idea.
- Keep the list SHORT (≤ ~12 names) and only genuine, level-defined setups.
- The bot reads this file; do NOT expect it to write it. You own it.

## Commit
Commit and push ALL written files (orders.json, latest.md, positions.md,
watchlist.json, and reports/today.md when applicable) DIRECTLY to `main`. No new
branch, no PR.
(Do NOT edit holdings.json or candidates.json — the bot owns those files.)
