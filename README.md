# schwab-trader → systematic ETF momentum bot 🤖📈

A fully automated, **backtested and out-of-sample validated** trading bot that runs on
GitHub Actions with nothing to babysit. It holds a trend-timed slice of the S&P 500 plus
a momentum rotation across 34 liquid ETFs, steps into T-bills when nothing is trending,
and trades once a day. **It runs today with zero accounts or keys** on a built-in
simulator; add [Alpaca](https://alpaca.markets) keys later to trade a real paper or live
account with the same code.

> Trading is risky. Nothing here is a guarantee of profit or financial advice. The
> numbers below are historical simulations with realistic costs, not promises.

**Setup: [SETUP.md](SETUP.md) · Rules: [STRATEGY.md](STRATEGY.md) · Evidence:
[reports/backtest.md](reports/backtest.md) and [reports/validation.md](reports/validation.md)
· Live view: [index.html](index.html) (enable GitHub Pages on the repo root)**

---

## What you get

| | |
|---|---|
| **Strategy** | Trend-timed core (50% in the strongest of SPY/QQQ/EFA while above its 150-day average) + top-8 momentum rotation over 34 ETFs in five staggered tranches, inverse-vol weights, 40% cluster cap, T-bills when defensive. Tuned to lose money less often. Every knob in `config.json`. |
| **Evidence** | 18-year backtest: **Sharpe 0.79 vs SPY 0.65, max drawdown -18% vs -52%**, losing months, 12-month stretches and time underwater all measured. Out-of-sample 2017–2026: +13.1%/yr, Sharpe 0.96. Bootstrap, sensitivity and timing-luck tests in `reports/validation.md`. Every idea that did not survive the backtest is documented there and switched off. |
| **Runs today** | No keys → the executor trades a built-in simulator at real prices and commits its book to the repo. The first run is already in `reports/today.md`. |
| **Broker** | Alpaca: static keys (no 7-day OAuth expiry), paper and live from the same code, fractional shares. |
| **Safety** | Long-only, never leveraged, sells before buys, one strategy step per day, only touches its own universe, 30% drawdown kill switch, broker-block detection, **stale-data guard** (no trades on old prices), **bad-tick guard** (a 25% "print" on an ETF is ignored), committed fallback data so a Yahoo outage cannot break a run. |
| **Ops** | `doctor.py` preflight on every run, a rolling **"📈 Trading log"** issue with every run, a **"🔴 Executor error"** issue with the traceback on any crash (auto-closed when healthy), a **watchdog** issue on a missed day, weekly backtest + validation refresh, CI tests on every push, a static dashboard. |
| **Real costs and taxes, measured** | Every fill is compared to the price the bot decided on (`signals/executions.json`); the track record shows average cost vs the backtest's 5 bps assumption, flags possible wash sales and reports holding periods. |
| **Intraday watch** | At 11:30 and 13:30 ET, `monitor.py` checks SPY/QQQ and every holding. On a big drop it opens a 🚨 issue and forces a fresh news scan for the afternoon decision. It deliberately never panic-sells: since 2000, after a -5% day SPY rose the next day 70% of the time. |
| **Credit-stress signal** | When junk bonds lag Treasuries (a classic early-warning sign), risk is halved. Used by the `conservative` and `guarded_growth` presets; off in `balanced`. |
| **More return, if you want it** | `aggressive` preset: half the book in a trend-timed 2x index fund. Backtest **+15.6%/yr since 2008 ($1k → $15k) vs SPY +11.4%**, with a -28% worst drawdown vs SPY's -52%. Same risk-adjusted return, bigger swings. See STRATEGY.md. |
| **Reads the news** | Every trading day at 15:35 ET, `news_brain.py` pulls ~180 fresh headlines (Google News, Yahoo Finance, MarketWatch) and Claude acts as a **risk officer**: it can lower risk on a crisis-grade event or veto up to 3 ETFs exposed to a specific shock, and it must cite the headlines. It can never buy anything. Every override is scored against what would have happened without it (`reports/track_record.md`). If it fails, the bot trades on the strategy alone. |

## Is it ready for real money?

**Not yet, and the code will refuse until it is.** Live trading is gated on three things
the executor checks itself (`bot.py: live_gate`):

1. **20 clean Alpaca paper runs** recorded in `signals/state.json` (`paper_clean_runs`).
   The simulator does not count; the real API has to be exercised for a month.
2. Repo variable **`MAX_CAPITAL`** set: an explicit dollar cap you chose on purpose.
3. Repo variable **`LIVE_CONFIRM`** equal to `I UNDERSTAND THE RISKS`.

What is verified today | What is not
---|---
Strategy logic, 18 years, walk-forward, bootstrap | Behaviour against Alpaca's *real* API (contract-tested against documented shapes only)
Executor end-to-end on a fake broker and the simulator | Real fills, real slippage, partial fills, settlement timing
No same-day sells (no day trades / PDT / good-faith violations) | A live account with pre-existing positions the bot does not manage
Deposits/withdrawals don't move the drawdown kill switch | Broker outages mid-rebalance (it reconciles next day, but untested for real)
Retry-safe orders (deterministic `client_order_id`) | Tax consequences of ~30 trades a year

`python doctor.py --probe` with paper keys sweeps every endpoint the bot uses and does a
$1 SPY buy/close round trip, so the API contract is proven before the first real dollar.

## How it works

```mermaid
flowchart LR
    S([GitHub schedule<br/>15:35 ET Mon-Fri]) --> T[trader.yml]
    T --> B[bot.py<br/>executor]
    C[(config.json)] --> B
    B -->|daily bars + live prices| D[(Alpaca data<br/>or Yahoo)]
    D --> ST[strategy.py]
    ST -->|target weights| B
    B <-->|positions / orders| A[(Alpaca account<br/>or broker_sim.py)]
    B --> F[(signals/ + reports/<br/>committed)]
    T --> AN[analyze.py] --> TR[(track_record.md)]
    T --> I[(📈 Trading log issue)]
    F --> DASH[index.html]
    W([watchdog.yml]) -.->|stall issue| F
    BT[backtest.py + validate.py] -.->|same code| ST
```

## Repo map

| File | What it is |
|------|------------|
| `strategy.py` | The rules as pure functions. `Params` = every knob. Optional sleeves (mean reversion, vol targeting, breadth regime, defensive momentum) are implemented, tested, and off. |
| `config.json` / `config.py` | Presets (`balanced`, `aggressive`, `growth`, `us_only`, `rotation_only`, `conservative`) and executor limits. Unknown keys are fatal on purpose. |
| `bot.py` | The executor. Picks Alpaca if keys exist, else the simulator. |
| `broker_sim.py` | File-backed simulator with the Alpaca interface, real prices, 5 bps slippage. |
| `alpaca.py` | Minimal stdlib Alpaca client (trading + data). |
| `data.py` | Keyless Yahoo daily bars with a local cache; `data_seed/` is a committed 2-year fallback (`python data.py --seed`). |
| `backtest.py` | Backtester + grids (`--grid`, `--grid2`, `--grid3`, `--grid4`). |
| `validate.py` | Walk-forward, sensitivity, timing luck, bootstrap, rolling windows → `reports/validation.md`. |
| `analyze.py` | Track record from the broker's fills and equity curve. |
| `doctor.py` | Preflight checklist (`--strict` for CI). |
| `watchdog.py` | Daily heartbeat check. |
| `index.html` | Dashboard. Serve the repo root (GitHub Pages → main, `/`). |
| `tests/` | 53 tests: indicators, targets, tranches, adaptive core, backtest/live parity, data guards, executor end-to-end on a fake broker and on the simulator. No network. |
| `signals/` | `state.json`, `targets.json`, `holdings.json`, `performance.json`, `sim_account.json`. |
| `reports/` | `backtest.md`, `validation.md`, `today.md`, `track_record.md`, `paper_ledger.md`. |
| `legacy/` | The retired Schwab + Claude-brain version. |

## Knobs

Edit `config.json` (then run `python backtest.py` to see what you did):

```json
{ "preset": "balanced",          // balanced | conservative | guarded_growth | aggressive | growth | us_only | rotation_only
  "strategy": { "mom_top_n": 6 },  // any strategy.Params field
  "executor": { "max_capital": null, "max_drawdown_halt": 0.30, "trade_window_min": 60 } }
```
Repo **variables** of the same name in upper case (`MAX_CAPITAL`, `MAX_DRAWDOWN_HALT`,
`TRADE_WINDOW_MIN`) override the file; `DRY_RUN=false` switches Alpaca to the live account.

## Run locally

```bash
python -m unittest discover -s tests -v   # 53 tests, no network, <1s
python doctor.py                          # preflight
python backtest.py --grid4                # candidate-defaults comparison
python validate.py                        # ~2 min, writes reports/validation.md
NO_TRADE=true FORCE_RUN=true python bot.py   # what would it do right now
python -m http.server                     # then open http://localhost:8000/index.html
```
Python 3.11, stdlib only.
