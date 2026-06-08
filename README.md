# schwab-trader 🤖📈

An AI-driven, guardrailed **day-trading bot** for Charles Schwab. A "brain" (Claude)
scans the market every few minutes, picks setups, and a separate executor places and
manages the trades — all running on GitHub Actions, no server to babysit.

> **Status: paper-trading experiment.** It ships in **paper mode** (`DRY_RUN=true`) — it
> simulates trades and tracks a P&L scorecard without touching real money. Prove it works
> on paper before ever going live. Trading is risky; you run this at your own risk.

**👉 To set up your own copy, follow [SETUP.md](SETUP.md).** This page explains what it is,
how it works, how to tune it, and where to see results.

---

## How it works

Three independent pieces, wired together through files in `signals/` and triggered by an
external cron. The **brain decides**, the **executor acts** — they never run in the same
process, so the bot can execute fast without the brain in the loop.

```mermaid
flowchart LR
    cron([cron-job.org<br/>every few min]) -->|triggers| BW[brain.yml]
    cron -->|triggers| TW[trader.yml]

    BW --> C[candidates.py<br/>gathers market funnel]
    C --> CJ[(signals/<br/>candidates.json)]
    CJ --> B{{Claude brain<br/>follows BRAIN.md}}
    H[(signals/<br/>holdings.json)] --> B
    B --> O[(signals/<br/>orders.json)]

    TW --> E[bot.py<br/>executor + guardrails]
    O --> E
    E <-->|live quotes / orders| S[(Schwab API)]
    E --> H
    E --> L[(reports/<br/>paper_ledger.md)]
    E --> A[analyze.py] --> TR[(reports/<br/>track_record.md)]

    WD([watchdog.yml]) -.->|alerts if it stalls| E
```

1. **`candidates.py`** builds a wide funnel — movers, upcoming earnings, trading halts, fresh
   SEC 8-Ks, news — into `signals/candidates.json`.
2. **The brain** (`.github/workflows/brain.yml` running Claude against **`BRAIN.md`**) reads that
   funnel + what it currently holds, researches, and writes its picks to `signals/orders.json`.
3. **`bot.py`** reads the picks, prices off Schwab's *live* quote, enforces the risk guardrails,
   and places/manages trades. It re-writes `holdings.json` (the brain's memory) and the P&L ledger.
4. **`analyze.py`** scores the closed trades (win rate, expectancy, by-signal breakdown).
5. **`watchdog.yml`** independently alerts you if the executor stops running during market hours.

---

## Repo map

| File | What it is |
|------|------------|
| **`bot.py`** | The executor. Places/exits trades, enforces all risk guardrails, manages the paper book. |
| **`candidates.py`** | Market-data funnel → `signals/candidates.json`. Pure stdlib, no Schwab needed. |
| **`BRAIN.md`** | **The strategy, in plain English.** Edit this to change how the brain thinks. |
| **`STRATEGY.md`** | The high-level risk rules / prime directive. |
| **`analyze.py`** | Track-record analyzer → `reports/track_record.md` (win rate, expectancy, attribution). |
| **`.github/workflows/`** | `brain.yml` (picks), `trader.yml` (executes), `watchdog.yml` (stall alert). |
| **`auth_setup.py`** | One-time Schwab OAuth login → refresh token. |
| **`accounts.py` / `place_order.py`** | Manual helpers: view balances, place a single order by hand. |
| **`config.py` / `schwab_session.py`** | Credential loading + authenticated Schwab client. |
| **`signals/`** | Live state the pieces pass between each other (orders, holdings, candidates, latest read). |
| **`reports/`** | Human-readable output: `paper_ledger.md` (P&L) and `track_record.md` (edge analysis). |
| **`SETUP.md`** | Step-by-step guide to run your own copy (built for a human *or* a Claude agent). |
| **`dashboard_cell.py` / `index.html`** | Optional viewers for your data (set your repo path inside). |

---

## ⚙️ Tune it (the knobs you'll actually touch)

Two ways to change behavior — pick whichever is easier:
- **Just ask your Claude:** e.g. *"change the per-trade cap to $200"* — these are all clearly
  labeled constants at the top of the file.
- **Or edit it yourself** — here's where each common knob lives:

| Want to change… | Set this | Where | Default |
|-----------------|----------|-------|---------|
| Paper vs. **real money** | `DRY_RUN` variable | GitHub repo Variables | `true` (paper) |
| **Max $ per trade** | `MAX_DOLLARS_PER_TRADE` | `bot.py` (top) | `150` |
| **Starting paper cash** | `PAPER_START_EQUITY` | `bot.py` (top) | `1000` |
| **Trading window** (buffer before/after the session) | `SESSION_BUFFER_MIN` | `bot.py` (top) | `60` min |
| **Penny-stock floor** | `MIN_SHARE_PRICE` | `bot.py` (top) | `$2` |
| **Anti-chase slippage cap** | `MAX_SLIPPAGE` | `bot.py` (top) | `5%` |
| **The actual strategy / how it picks** | edit the prose | **`BRAIN.md`** | — |
| Funnel sources & limits | the `KNOBS` block | `candidates.py` (top) | — |

The whole strategy is **plain-English in `BRAIN.md`** — change the trading style by editing that
file, no code required.

---

## 📊 Where to see results

After it runs, check these (they auto-update each cycle):
- **`reports/paper_ledger.md`** — running equity, cash, open positions, realized P&L, every closed trade.
- **`reports/track_record.md`** — the edge analysis: win rate, **expectancy**, drawdown, and a
  breakdown of which *signals* actually make money.
- **`signals/latest.md`** — the brain's reasoning for the most recent run (what it saw, why it picked).

---

## ❓ Troubleshooting / FAQ

| Symptom | Cause & fix |
|---------|-------------|
| Bot runs fail with **`invalid_grant` / HTTP 400** | The Schwab refresh token expired (~7-day limit). Re-run `python auth_setup.py` and update the `SCHWAB_REFRESH_TOKEN` secret. |
| **"Market CLOSED — no-op"** in the logs | Working as intended — the bot only trades **08:30–17:00 ET**, Mon–Fri. |
| **No trades / nothing happening** | Check: `DRY_RUN` value, market hours, the token is valid, and `signals/orders.json` is fresh. |
| **Weak or empty picks** | Missing `FMP_API_KEY` / `ALPHA_API_KEY` — the funnel degrades without them. |
| **Brain never runs** | `CLAUDE_CODE_OAUTH_TOKEN` secret isn't set (see SETUP.md). |
| Bot stopped and nobody noticed | The `executor-watchdog` workflow opens an alert issue when it stalls during market hours. |
| **How do I go live?** | Only after `track_record.md` shows positive expectancy over a real sample — then set `DRY_RUN=false`. See SETUP.md. |
| **How do I change the strategy?** | Edit **`BRAIN.md`** (plain English) and `STRATEGY.md`. No code needed. |

---

## Running the manual scripts locally (optional)

The repo also includes hand-operated helpers (not needed for the automated bot):

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in your Schwab app key/secret
python auth_setup.py          # one-time login -> token.json
python accounts.py            # view balances & positions
python place_order.py BUY AAPL 1 185.00   # place one order by hand
```
