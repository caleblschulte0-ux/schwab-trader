# SETUP — run your own copy

Time: ~15 minutes. Cost: $0 (Alpaca paper trading and its basic data feed are free).

## 1. Alpaca account **[HUMAN]**
1. Sign up at https://app.alpaca.markets. You get a **paper** account immediately; a live
   account needs the usual brokerage KYC and funding.
2. In the dashboard, switch to **Paper** (top-left) → *Reset* the paper balance to
   **$1,000** so paper results match what you would fund live (or leave $100k and set
   `MAX_CAPITAL=1000` in step 3).
3. **API Keys** → *Generate*. Copy the key and secret. These do **not** expire.
   (Live trading later uses a separate pair generated while the dashboard is in *Live* mode.)

## 2. GitHub secrets **[HUMAN]**
Repo → Settings → Secrets and variables → Actions:

**Secrets**
```
ALPACA_API_KEY        ALPACA_SECRET_KEY
CLAUDE_CODE_OAUTH_TOKEN   (optional: enables the weekly analyst note only; not needed to trade)
```
**Variables**
```
DRY_RUN            = true     # paper. Set to false for the live account (with LIVE keys).
MAX_CAPITAL        = 1000     # optional cap on the dollars the bot manages
MAX_DRAWDOWN_HALT  = 0.20     # optional; kill switch threshold
TRADE_WINDOW_MIN   = 120      # optional; minutes before close the bot may trade
```
The old `SCHWAB_*`, `FMP_API_KEY`, `ALPHA_API_KEY` secrets are no longer used and can be deleted.

## 3. Turn it on **[HUMAN]**
The `trader` workflow runs itself on GitHub's schedule at 15:35 ET every weekday
(no cron-job.org needed; if you still have cron-job.org jobs pointed at the old
workflows, delete them). To see it work right now:

- Actions → **trader** → *Run workflow* → tick **no_trade** → Run.
  It logs the target portfolio it would buy and writes `reports/today.md` + `signals/targets.json`.
- During market hours (any time, with **force_run** ticked; or in the last two hours without),
  run it again without `no_trade`: it buys the targets in the paper account.

## 4. Verify
- `reports/today.md` — the run log (targets, orders, fills).
- `signals/holdings.json` — the account snapshot.
- Alpaca dashboard → Paper → Positions should match `signals/targets.json` weights.
- `reports/track_record.md` fills in from the broker's books after the first fills.
- The **watchdog** workflow opens an issue titled "Executor stalled" if a trading day
  passes without a run; it closes it when the bot is back.

## 5. Going live (deliberately) **[HUMAN]**
1. Fund the live account. Generate **Live** API keys and replace the two secrets.
2. Set `DRY_RUN=false`.
3. Keep `MAX_CAPITAL` at what you are comfortable losing 20% of. The kill switch is a
   backstop, not a promise.

## Local use
```bash
python -m unittest discover -s tests -v
python backtest.py --grid
ALPACA_API_KEY=... ALPACA_SECRET_KEY=... NO_TRADE=true FORCE_RUN=true python bot.py
```
No dependencies beyond Python 3.11 (stdlib only).
