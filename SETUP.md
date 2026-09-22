# SETUP

## 0. It already runs
Merge to `main` and the `trader` workflow runs every weekday at 15:35 ET on the built-in
**simulator** (real prices, no accounts). Watch it in:
- the **📈 Trading log** issue (one comment per run),
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

## 3. Going live **[HUMAN]**
1. Fund the live account; generate **Live** keys; replace the two secrets.
2. Set repo variable `DRY_RUN=false`.
3. Keep `MAX_CAPITAL` at what you can watch fall 30% without touching the keyboard.

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
