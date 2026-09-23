# SETUP

## 0. It already runs
Merge to `main` and the `trader` workflow runs every 30 minutes through each weekday session (trading once per day) on the built-in
**simulator** (real prices, no accounts). Watch it in:
- the **📈 Trading log** issue (one comment per run); a **🔴 Executor error** issue appears
  only if a run crashes and closes itself when the next run is clean,
- `reports/today.md`, `signals/targets.json`, `reports/track_record.md`,
- the dashboard: Settings → Pages → *Deploy from branch* → `main` / `/ (root)`, then open
  the Pages URL.

Optional repo **variables** (Settings → Secrets and variables → Actions → Variables):
`MAX_CAPITAL`, `MAX_DRAWDOWN_HALT`, `TRADE_WINDOW_MIN`. Everything else is in `config.json`.

## 1. Alpaca (when you're ready for a real paper or live account) **[HUMAN]**
1. Sign up at https://app.alpaca.markets. The paper account is instant and free.
2. Dashboard → **Paper** → *Reset* the balance to $1,000 (or set `MAX_CAPITAL=1000`).
3. **API Keys** → *Generate*. They do not expire.
4. Repo → Settings → Secrets → add `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`.
   The next run switches from the simulator to the paper account automatically.
   (Delete the old `SCHWAB_*`, `FMP_API_KEY`, `ALPHA_API_KEY` secrets; nothing reads them.)

## 2. Verify
- Actions → **trader** → *Run workflow* with **no_trade** ticked: logs the targets, no orders.
- `python doctor.py` locally (or read its output in the workflow) for a preflight checklist.
- The **watchdog** workflow opens an issue if a trading day passes without a run.

## 3. Going live **[HUMAN]** — the bot enforces this order
1. **Burn in on paper.** After adding paper keys, let it run for **20 trading days**
   (`signals/state.json` → `paper_clean_runs`). Read the Trading log. Compare
   `signals/holdings.json` to the Alpaca dashboard.
2. **Probe the API** once during market hours: locally,
   `ALPACA_API_KEY=... ALPACA_SECRET_KEY=... python doctor.py --probe`
   (paper keys only; it does a $1 SPY buy/close and sweeps every endpoint).
3. Fund the live account; generate **Live** keys; replace the two secrets.
4. Set repo variables `MAX_CAPITAL` (the dollars you can watch fall 30%),
   `LIVE_CONFIRM` = `I UNDERSTAND THE RISKS`, then `DRY_RUN=false`.
   Missing any of these → the run logs "LIVE requested but REFUSED" and exits non-zero
   (which opens the error issue, so you will notice).
5. The live account should hold nothing but what the bot manages, or set `MAX_CAPITAL`
   well below its equity; positions outside the ETF universe are ignored, never sold.

## The news layer
Add **one** of these secrets so the daily news scan can run (it is skipped otherwise):
- `ANTHROPIC_API_KEY` — an Anthropic API key (about one short call per trading day), or
- `CLAUDE_CODE_OAUTH_TOKEN` — your Claude subscription token (`claude setup-token`).

## Optional: weekly Claude review
Add `CLAUDE_CODE_OAUTH_TOKEN` and `analyst.yml` writes `reports/analyst.md` every Friday.
It cannot trade and the bot never waits for it.

## Local
```bash
python -m unittest discover -s tests -v
python doctor.py
NO_TRADE=true FORCE_RUN=true python bot.py
```
Python 3.11, stdlib only. `.env.example` lists every variable.
