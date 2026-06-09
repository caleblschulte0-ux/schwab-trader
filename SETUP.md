# SETUP — running your own copy of this trading bot

This repo is an **automated paper/live stock-trading bot** that runs on GitHub Actions,
triggered by an external cron. It has **two Claude brains** (one buys, one sells) and an executor:

- **`candidates.py`** gathers a market-data funnel (movers, earnings, halts, SEC 8-Ks, news).
- **The BUY brain** (`.github/workflows/brain.yml`) runs Claude headless against `BRAIN.md` to pick buys.
- **The SELL brain** (`.github/workflows/sell-brain.yml`) runs Claude against `SELL_BRAIN.md` to decide
  exits by *judgment* — `route_sells.py` then sells routine names on its own and only opens a GitHub
  issue asking you to **approve** selling a *significant* position (`approve-sell.yml` handles your reply).
- **`bot.py`** executes the buys + approved/autonomous sells against Schwab (paper by default), with
  hard risk guardrails. There are **no mechanical stop-losses** — exits are the sell brain's job.

> ⚠️ **It starts in PAPER mode (`DRY_RUN=true`) — no real money.** Keep it there until
> you've watched it work and *seen a positive track record*. Read `STRATEGY.md` and `BRAIN.md`.
> Trading real money is risky and entirely at your own risk. This is not financial advice.

---

## 🤖 If you are a Claude / AI agent setting this up

Do the steps you *can* do directly, and **stop and ask the human** for the steps marked
**[HUMAN]** (creating accounts, browser logins, pasting secrets). Suggested order:

1. **[AGENT]** Run "Step 1 — Start from a clean slate" below (wipe the previous owner's data).
2. **[AGENT]** Replace `YOUR_GITHUB_USERNAME/YOUR_REPO` in `dashboard_cell.py`, `index.html`,
   and `README.md` with this repo's actual `owner/name`.
3. **[HUMAN]** Create the accounts in "Step 2" and hand back the keys.
4. **[HUMAN]** Add the GitHub **secrets/variables** in "Step 3" (or run the `gh secret set`
   commands if `gh` is authenticated).
5. **[HUMAN]** Do the one-time Schwab login in "Step 4" (`python auth_setup.py`) and give the
   agent the resulting refresh token to store as a secret.
6. **[HUMAN]** Set up the cron triggers in "Step 5".
7. **[AGENT]** Verify with "Step 6" and report status.

Never invent or hard-code any secret. Never flip `DRY_RUN` to `false` without explicit human approval.

---

## Step 1 — Start from a clean slate  *(removes the previous owner's paper data)*

The template copies the previous owner's paper history. Reset it — the code regenerates
clean files automatically on the next run:

```bash
rm -f signals/holdings.json signals/paper_account.json signals/orders.json \
      signals/watchlist.json signals/candidates.json signals/latest.md \
      signals/positions.md signals/performance.json \
      signals/proposed_sells.json signals/sell_orders.json \
      signals/pending_sells.json signals/sell_review.md \
      reports/paper_ledger.md reports/today.md reports/track_record.md
git add -A && git commit -m "reset state to clean slate" && git push
```

The paper book restarts at $1,000 (change `PAPER_START_EQUITY` in `bot.py` if you want).

---

## Step 2 — Create the accounts you need  **[HUMAN]**

You need your **own** keys for everything — never reuse anyone else's (their keys = access
to *their* money). Plan for a few days: the Schwab developer approval is the long pole.

| # | Account | What you get | Notes |
|---|---------|--------------|-------|
| 1 | [Schwab Developer Portal](https://developer.schwab.com) | `APP_KEY`, `APP_SECRET` | **Approval takes days.** Register a Trader API app; set the callback URL to `https://127.0.0.1/`. |
| 2 | A Schwab brokerage account | the account the bot trades | Needed even for paper mode (the bot pulls **live Schwab quotes**). |
| 3 | [FinancialModelingPrep](https://financialmodelingprep.com) | `FMP_API_KEY` | Free tier. Powers movers/earnings funnel. |
| 4 | [Alpha Vantage](https://www.alphavantage.co/support/#api-key) | `ALPHA_API_KEY` | Free tier (25 calls/day). Powers the news funnel. |
| 5 | A **Claude subscription** + Code OAuth token | `CLAUDE_CODE_OAUTH_TOKEN` | Run `claude setup-token` (Claude Code CLI). Powers the brain. Recurring cost. |
| 6 | [cron-job.org](https://cron-job.org) (or any cron service) | triggers the workflows | Free. See Step 5. |

Without 3/4/5 the bot still runs but the funnel/brain are weak or off. 1 and 2 are required.

---

## Step 3 — Add secrets & variables to GitHub  **[HUMAN]**

In your repo: **Settings → Secrets and variables → Actions**.

**Secrets** (Secrets tab):
```
SCHWAB_APP_KEY            SCHWAB_APP_SECRET            SCHWAB_REFRESH_TOKEN   (from Step 4)
FMP_API_KEY              ALPHA_API_KEY                CLAUDE_CODE_OAUTH_TOKEN
```
**Variables** (Variables tab):
```
DRY_RUN = true        # PAPER mode. Leave true until you're ready. Set false to go LIVE.
```

If you use the GitHub CLI, an agent can set secrets for you once `gh` is authenticated:
```bash
gh secret set SCHWAB_APP_KEY        # then paste the value when prompted
gh secret set SCHWAB_APP_SECRET
gh secret set SCHWAB_REFRESH_TOKEN
gh secret set FMP_API_KEY
gh secret set ALPHA_API_KEY
gh secret set CLAUDE_CODE_OAUTH_TOKEN
gh variable set DRY_RUN --body "true"
```

---

## Step 4 — One-time Schwab login  **[HUMAN]**

Locally (or in the Colab notebook `schwab_colab.ipynb`):
```bash
cp .env.example .env        # then fill in SCHWAB_APP_KEY / SCHWAB_APP_SECRET
pip install -r requirements.txt
python auth_setup.py        # opens a Schwab login URL; paste the redirect URL back
```
This writes `token.json` and prints/refreshes a **refresh token**. Put that value in the
`SCHWAB_REFRESH_TOKEN` secret (Step 3).

> 🔁 **The Schwab refresh token expires every ~7 days.** When the bot starts failing with
> `invalid_grant`, re-run `python auth_setup.py` and update the secret. This is a Schwab
> limitation, not a bug. (The repo includes a `executor-watchdog` workflow that alerts when
> the bot stops running during market hours.)

---

## Step 5 — Set up the cron triggers  **[HUMAN]**

The workflows only run when something calls their `workflow_dispatch`. Create **three**
cron-job.org jobs that POST to the GitHub API (set the job timezone to **America/Chicago**):

- **Trader** (`trader.yml`) — every 5 min, market hours + buffer: crontab `*/5 7-16 * * 1-5`
- **Buy brain** (`brain.yml`) — a few times/hour: crontab `7,27,47 8-15 * * 1-5`
- **Sell brain** (`sell-brain.yml`) — staggered off the buy brain: crontab `15,45 8-15 * * 1-5`

Each cron job is an HTTP **POST** to:
`https://api.github.com/repos/<owner>/<repo>/actions/workflows/<file>.yml/dispatches`
with header `Authorization: Bearer <a GitHub fine-grained PAT with Actions: read/write>`
and JSON body `{"ref":"main"}`. The **only** thing that differs between the three jobs is the
`<file>.yml` in the URL — same token, same headers, same body. (Tip: make one job, then
**duplicate** it twice and change the filename + schedule.)

(The `executor-watchdog` workflow runs on GitHub's own schedule — no cron-job.org needed for it.
`approve-sell.yml` is event-driven off your issue comment — it needs no cron either.)

The bot **only trades 08:30–17:00 ET** regardless of when it's poked (`in_trading_window` in
`bot.py`), so off-hours pokes just no-op safely.

---

## Step 6 — Verify  **[AGENT or HUMAN]**

- **Actions tab** → manually run **schwab-trader-bot**. In paper mode it should log
  `mode: DRY-RUN`, read/write the paper book, and finish green.
- Check `reports/paper_ledger.md` (running P&L) and `reports/track_record.md` (edge analysis)
  update after runs.
- Manually run **schwab-trader-brain** once `CLAUDE_CODE_OAUTH_TOKEN` is set; it should write
  `signals/orders.json` + `signals/latest.md`.
- Manually run **schwab-trader-sell-brain**; it should write `signals/proposed_sells.json` +
  `signals/sell_review.md` (and, if it wants to exit a significant position, open a
  "🤔 Sell approval needed" issue you can reply to with `approve`).

---

## Going live (later, deliberately)  **[HUMAN]**

Only after the paper `track_record.md` shows **positive expectancy over a real sample** (≥ ~20–30
closed trades): set the `DRY_RUN` variable to `false`. Options stay paper-only unless you also set
`OPTIONS_LIVE=true`. Start small. The code enforces: BUY-only, never short, a per-trade dollar cap,
a price floor, and a slippage backstop — but **you** are responsible for the money.
