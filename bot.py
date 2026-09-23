#!/usr/bin/env python3
"""The executor. Runs once per trading day (last hour of the session), computes the
strategy's target portfolio, and reconciles the Alpaca account to it.

    python bot.py                 # paper (DRY_RUN=true) or live (DRY_RUN=false)
    NO_TRADE=true python bot.py   # compute + report, submit nothing
    FORCE_RUN=true python bot.py  # ignore the market-hours / trade-window guard

Environment
  ALPACA_API_KEY, ALPACA_SECRET_KEY   Alpaca keys. WITHOUT them the bot trades the built-in
                     simulator (broker_sim.py) at Yahoo prices, so the system runs end to end
                     and builds a track record before any brokerage exists.
  DRY_RUN            "true" (default) -> paper-api.alpaca.markets; "false" -> real money
  MAX_CAPITAL        cap on the dollars this bot manages (default: whole account equity)
  TRADE_WINDOW_MIN   only trade within this many minutes of the close (default 60)
  MAX_DRAWDOWN_HALT  kill switch: liquidate + halt if equity falls this far below its
                     high-water mark (default 0.30; see reports/validation.md for why not
                     0.20). Reset by deleting "halted" from signals/state.json.
  Knobs also live in config.json (preset, strategy overrides, executor limits); env wins.
  MIN_TRADE_DOLLARS  ignore rebalance deltas smaller than this (default 5)
  NO_TRADE / FORCE_RUN   see above

Files (committed by the workflow so the repo is the audit trail)
  signals/state.json     strategy state + high-water mark + last run/trade dates
  signals/targets.json   today's target weights and the strategy's notes
  signals/holdings.json  account snapshot (positions, cash, equity)
  reports/today.md       human-readable log of the last run

Safety rails (in code, not prose): never leveraged, never short, only touches symbols in
the strategy universe (other holdings in the account are ignored, not sold), sells before
buys, buys capped to settled cash, one strategy step per trading day, drawdown kill switch.
"""
from __future__ import annotations

import json
import math
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import config as cfgmod
import news_overlay
import data as datamod
from alpaca import Alpaca, AlpacaError
from broker_sim import SimBroker
from strategy import LEVERAGED, UNIVERSE, Params, State, compute_targets

SIGNALS_DIR = "signals"
REPORTS_DIR = "reports"
STATE_FILE = os.path.join(SIGNALS_DIR, "state.json")
TARGETS_FILE = os.path.join(SIGNALS_DIR, "targets.json")
HOLDINGS_FILE = os.path.join(SIGNALS_DIR, "holdings.json")
TODAY_FILE = os.path.join(REPORTS_DIR, "today.md")
NEWS_FILE = os.path.join(SIGNALS_DIR, "news_risk.json")
NEWS_LOG = os.path.join(SIGNALS_DIR, "news_log.json")

HISTORY_DAYS = 420  # calendar days of bars to load (>= 260 trading days + slack)
MAX_DAILY_MOVE = 0.25       # bad-tick guard for live prices
MAX_BAR_AGE_DAYS = 5        # stale-data guard: newest bar must be within this many days
MIN_LIVE_COVERAGE = 0.80    # stale-data guard: live prices needed for this share of symbols


class StaleData(RuntimeError):
    pass


def env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def env_float(name: str, default: Optional[float]) -> Optional[float]:
    v = os.environ.get(name, "").strip()
    if not v:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def parse_ts(s: str) -> datetime:
    """Alpaca timestamps may carry nanoseconds; trim to microseconds for fromisoformat."""
    s = s.replace("Z", "+00:00")
    if "." in s:
        head, rest = s.split(".", 1)
        frac = ""
        tz = ""
        for i, ch in enumerate(rest):
            if ch.isdigit():
                frac += ch
            else:
                tz = rest[i:]
                break
        s = f"{head}.{frac[:6].ljust(6, '0')}{tz}"
    return datetime.fromisoformat(s)


def load_json(path: str, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


class Log:
    def __init__(self):
        self.lines: List[str] = []

    def __call__(self, msg: str) -> None:
        print(msg, flush=True)
        self.lines.append(msg)


# ----------------------------------------------------------------------------- #
# Data                                                                          #
# ----------------------------------------------------------------------------- #
def load_market_history(api: Alpaca, symbols: List[str], today_et: str, log: Log) -> Dict[str, List[float]]:
    """symbol -> closes oldest..newest with today's live price as the last element."""
    start = (datetime.strptime(today_et, "%Y-%m-%d") - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    yesterday = (datetime.strptime(today_et, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    bars: Dict[str, List[Tuple[str, float]]] = {}
    try:
        bars = api.daily_bars(symbols, start=start, end=yesterday, adjustment="all")
        n_ok = sum(1 for s in symbols if len(bars.get(s, [])) >= 200)
        log(f"(data) broker bars: {n_ok}/{len(symbols)} symbols with >=200 bars")
        if n_ok < len(symbols) // 2:
            raise RuntimeError("too few symbols from broker bars")
    except Exception as exc:  # noqa: BLE001
        log(f"(data) broker bars unavailable ({exc}); falling back to Yahoo")
        yh = datamod.load_history(symbols, refresh=True, max_age_hours=None)
        bars = {s: [(d, c) for d, c in v if d <= yesterday] for s, v in yh.items()}

    live: Dict[str, float] = {}
    try:
        live = api.latest_prices(symbols)
        log(f"(data) live prices for {len(live)}/{len(symbols)} symbols")
    except Exception as exc:  # noqa: BLE001
        log(f"(data) live prices unavailable ({exc}); using last close")

    hist: Dict[str, List[float]] = {}
    suspect: List[str] = []
    for s in symbols:
        closes = [c for _, c in bars.get(s, [])]
        if not closes:
            continue
        p = live.get(s)
        if p:
            # Bad-tick guard: an ETF does not move 25% in a day. Treat it as a data glitch,
            # mark from the last close instead, and say so.
            if abs(p / closes[-1] - 1.0) > MAX_DAILY_MOVE:
                suspect.append(f"{s} {p:.2f} vs {closes[-1]:.2f}")
                p = closes[-1]
            closes.append(p)
        hist[s] = closes
    if suspect:
        log(f"(data) suspect live prices ignored: {', '.join(suspect)}")

    # Stale-data guard: never trade on old prices. Bars must reach the previous session
    # and live prices must cover nearly the whole universe, else this run only snapshots.
    last_bar = max((str(bars[s][-1][0])[:10] for s in symbols if bars.get(s)), default="1970-01-01")
    try:
        age_days = (datetime.strptime(today_et, "%Y-%m-%d") - datetime.strptime(last_bar, "%Y-%m-%d")).days
    except ValueError:
        age_days = 999  # unparseable bar date -> treat as stale
    coverage = len(live) / max(1, len(symbols))
    if age_days > MAX_BAR_AGE_DAYS or coverage < MIN_LIVE_COVERAGE:
        raise StaleData(f"last bar {last_bar} ({age_days}d old), live coverage {coverage:.0%}")
    return hist


LIVE_PHRASE = "I UNDERSTAND THE RISKS"


def live_gate(ex: dict, st: dict) -> List[str]:
    """Reasons LIVE trading is refused (empty list = allowed). All must be satisfied."""
    reasons = []
    if os.environ.get("LIVE_CONFIRM", "").strip() != LIVE_PHRASE:
        reasons.append(f'repo variable LIVE_CONFIRM must be exactly "{LIVE_PHRASE}"')
    if not ex.get("max_capital"):
        reasons.append("MAX_CAPITAL must be set for live trading (an explicit dollar cap)")
    need = int(ex.get("live_min_paper_runs") or 0)
    have = int(st.get("paper_clean_runs", 0) or 0)
    if have < need:
        reasons.append(f"only {have}/{need} clean Alpaca PAPER runs recorded (burn-in not complete)")
    return reasons


# ----------------------------------------------------------------------------- #
# Reconciliation                                                                #
# ----------------------------------------------------------------------------- #
def plan_orders(targets: Dict[str, float], current: Dict[str, float], min_trade: float,
                no_sell: Optional[set] = None) -> List[Tuple[str, str, float]]:
    """[(symbol, 'sell'|'buy'|'close', dollars)] -- sells first, largest first.
    `no_sell`: symbols bought today; never sold the same day (no day trades, no PDT flags,
    no good-faith violations on a cash account)."""
    plan: List[Tuple[str, str, float]] = []
    no_sell = no_sell or set()
    for s in sorted(set(targets) | set(current)):
        tgt = targets.get(s, 0.0)
        cur = current.get(s, 0.0)
        delta = tgt - cur
        if delta < 0 and s in no_sell:
            continue
        if tgt <= 0 and cur > 0:
            plan.append((s, "close", cur))
        elif delta <= -min_trade:
            plan.append((s, "sell", -delta))
        elif delta >= min_trade:
            plan.append((s, "buy", delta))
    sells = sorted([o for o in plan if o[1] in ("close", "sell")], key=lambda o: -o[2])
    buys = sorted([o for o in plan if o[1] == "buy"], key=lambda o: -o[2])
    return sells + buys


def execute(api: Alpaca, plan: List[Tuple[str, str, float]], prices: Dict[str, float], log: Log,
            no_trade: bool, asset_cache: Dict[str, dict], tag: str = "") -> List[dict]:
    fills: List[dict] = []

    def coid(sym: str, side: str, amt: float) -> str:
        return f"{tag}-{sym}-{side}-{int(round(amt))}"[:48]
    # ---- sells / closes
    for sym, kind, dollars in [o for o in plan if o[1] != "buy"]:
        if no_trade:
            log(f"  [no-trade] would {kind.upper()} {sym} ${dollars:,.2f}")
            continue
        try:
            if kind == "close":
                o = api.close_position(sym)
            else:
                o = api.submit_order(sym, "sell", notional=round(dollars, 2), client_order_id=coid(sym, "sell", dollars))
            o = api.wait_for_fill(o["id"])
            log(f"  {kind.upper()} {sym} ${dollars:,.2f} -> {o.get('status')} filled_qty={o.get('filled_qty')} avg={o.get('filled_avg_price')}")
            fills.append(o)
        except AlpacaError as e:
            log(f"  {kind.upper()} {sym} FAILED: {e}")
    # ---- buys, capped to settled cash
    buys = [o for o in plan if o[1] == "buy"]
    if not buys:
        return fills
    if no_trade:
        for sym, _, dollars in buys:
            log(f"  [no-trade] would BUY {sym} ${dollars:,.2f}")
        return fills
    acct = api.account()
    cash = max(0.0, float(acct.get("cash", 0.0)))
    spendable = cash * 0.998  # leave a sliver for price drift between quote and fill
    for sym, _, dollars in buys:
        amt = math.floor(min(dollars, spendable) * 100) / 100.0
        if amt < 1.0:
            log(f"  BUY {sym} skipped: out of cash (${spendable:,.2f} left)")
            continue
        try:
            a = asset_cache.get(sym) or api.asset(sym)
            asset_cache[sym] = a
            if not a.get("tradable", True):
                log(f"  BUY {sym} skipped: not tradable")
                continue
            if a.get("fractionable", False):
                o = api.submit_order(sym, "buy", notional=round(amt, 2), client_order_id=coid(sym, "buy", amt))
            else:
                px = prices.get(sym) or 0.0
                qty = int(amt // px) if px > 0 else 0
                if qty < 1:
                    log(f"  BUY {sym} skipped: not fractionable and ${amt:,.2f} < 1 share (${px:,.2f})")
                    continue
                o = api.submit_order(sym, "buy", qty=qty, client_order_id=coid(sym, "buy", amt))
                amt = qty * px
            o = api.wait_for_fill(o["id"])
            spent = float(o.get("filled_avg_price") or 0) * float(o.get("filled_qty") or 0) or amt
            spendable -= spent
            log(f"  BUY {sym} ${amt:,.2f} -> {o.get('status')} filled_qty={o.get('filled_qty')} avg={o.get('filled_avg_price')}")
            fills.append(o)
        except AlpacaError as e:
            log(f"  BUY {sym} FAILED: {e}")
    return fills


# ----------------------------------------------------------------------------- #
# Snapshots                                                                     #
# ----------------------------------------------------------------------------- #
def write_holdings(api: Alpaca, managed: set, now_utc: str, log: Log) -> dict:
    acct = api.account()
    pos = api.positions()
    rows = []
    for p in sorted(pos, key=lambda x: x["symbol"]):
        rows.append({
            "symbol": p["symbol"],
            "qty": float(p.get("qty", 0)),
            "avg_entry": float(p.get("avg_entry_price", 0)),
            "last": float(p.get("current_price", 0) or 0),
            "market_value": float(p.get("market_value", 0) or 0),
            "unrealized_pl": float(p.get("unrealized_pl", 0) or 0),
            "unrealized_pct": round(float(p.get("unrealized_plpc", 0) or 0) * 100, 2),
            "managed": p["symbol"] in managed,
        })
    snap = {
        "updated_utc": now_utc,
        "mode": getattr(api, "mode", "paper" if getattr(api, "paper", True) else "LIVE"),
        "equity": float(acct.get("equity", 0)),
        "cash": float(acct.get("cash", 0)),
        "buying_power": float(acct.get("buying_power", 0)),
        "positions": rows,
    }
    save_json(HOLDINGS_FILE, snap)
    return snap


def write_today(log: Log, header: str) -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(TODAY_FILE, "w") as f:
        f.write(f"# Executor run — {header}\n\n```\n" + "\n".join(log.lines) + "\n```\n")


# ----------------------------------------------------------------------------- #
# Main                                                                          #
# ----------------------------------------------------------------------------- #
def main() -> int:
    log = Log()
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    dry_run = env_bool("DRY_RUN", True)
    no_trade = env_bool("NO_TRADE", False)
    force = env_bool("FORCE_RUN", False)
    cfg = cfgmod.load_config()
    params, preset = cfgmod.build_params(cfg)
    ex = cfgmod.executor_settings(cfg)
    window_min = ex["trade_window_min"]
    max_capital = ex["max_capital"]
    dd_halt = ex["max_drawdown_halt"]
    min_trade = ex["min_trade_dollars"]

    if key and secret:
        api = Alpaca(key, secret, paper=dry_run)
        mode = "PAPER" if dry_run else "LIVE"
        api.mode = mode.lower()
        if mode == "LIVE":
            gate = live_gate(ex, load_json(STATE_FILE, {}))
            if gate:
                log("=== Executor | LIVE requested but REFUSED ===")
                for g in gate:
                    log(f"  - {g}")
                write_today(log, "live refused")
                return 1
    else:
        api = SimBroker(start_cash=ex["sim_start_cash"])
        mode = "SIM"
    log(f"=== Executor | {mode}{' | NO_TRADE' if no_trade else ''} | preset={preset} | {datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z ===")
    if mode == "SIM":
        log("no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. "
            "Add Alpaca keys (SETUP.md) to trade a real paper/live account.")
    clock = api.clock()
    now = parse_ts(clock["timestamp"])
    now_utc = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today_et = now.strftime("%Y-%m-%d")  # clock timestamp is in exchange (ET) offset
    next_close = parse_ts(clock["next_close"])
    minutes_to_close = (next_close - now).total_seconds() / 60.0
    is_open = bool(clock.get("is_open"))

    managed = set(UNIVERSE) | set(LEVERAGED.values()) | ({params.cash_proxy} if params.cash_proxy else set())
    st_raw = load_json(STATE_FILE, {})
    st_raw["last_seen_date"] = today_et
    st_raw["last_mode"] = mode
    state = State.from_dict(st_raw.get("strategy"))
    hwm = float(st_raw.get("hwm", 0.0) or 0.0)

    # ------------------------------------------------------------ guards
    if st_raw.get("halted"):
        log(f"HALTED since {st_raw.get('halted_at')}: {st_raw.get('halt_reason')}. "
            "Delete the 'halted' key in signals/state.json to resume.")
        write_holdings(api, managed, now_utc, log)
        write_today(log, "halted")
        return 0

    in_window = is_open and minutes_to_close <= window_min
    if not (in_window or force):
        why = "market closed" if not is_open else f"{minutes_to_close:.0f} min to close (> {window_min:.0f}-min trade window)"
        log(f"Outside trade window ({why}) -- refreshing snapshot only. next_close={clock['next_close']}")
        if hasattr(api, "snapshot"):
            api.snapshot()
        snap = write_holdings(api, managed, now_utc, log)
        log(f"equity=${snap['equity']:,.2f} cash=${snap['cash']:,.2f} positions={len(snap['positions'])}")
        st_raw["last_run_utc"] = now_utc
        save_json(STATE_FILE, st_raw)
        write_today(log, f"{today_et} no-op")
        return 0

    acct = api.account()
    if acct.get("trading_blocked") or acct.get("account_blocked"):
        log(f"Account blocked by broker (trading_blocked={acct.get('trading_blocked')}); no orders.")
        write_today(log, f"{today_et} blocked")
        return 1
    equity = float(acct["equity"])
    cash = float(acct["cash"])
    # External money movements are not performance: shift the high-water mark by the net
    # flow so a withdrawal cannot look like a crash (and a deposit cannot hide one).
    flows = 0.0
    if st_raw.get("last_run_utc"):
        try:
            flows = float(api.cash_flows(after=st_raw["last_run_utc"]))
        except Exception as exc:  # noqa: BLE001
            log(f"(warn) could not read cash flows ({exc}); assuming none")
    if abs(flows) >= 1.0 and hwm > 0:
        log(f"external cash flow since last run: {flows:+,.2f} -> high-water mark {hwm:,.2f} -> {hwm + flows:,.2f}")
        hwm = max(0.0, hwm + flows)
    hwm = max(hwm, equity)
    capital = min(equity, max_capital) if max_capital else equity
    log(f"account: equity=${equity:,.2f} cash=${cash:,.2f} hwm=${hwm:,.2f} managed_capital=${capital:,.2f} "
        f"| {minutes_to_close:.0f} min to close")

    # ------------------------------------------------------------ kill switch
    if hwm > 0 and equity < hwm * (1.0 - dd_halt):
        reason = f"equity ${equity:,.2f} is {equity / hwm - 1:.1%} below high-water mark ${hwm:,.2f} (limit -{dd_halt:.0%})"
        log(f"KILL SWITCH: {reason}. Liquidating managed positions and halting.")
        if not no_trade:
            for p in api.positions():
                if p["symbol"] in managed:
                    try:
                        api.close_position(p["symbol"])
                        log(f"  closed {p['symbol']}")
                    except AlpacaError as e:
                        log(f"  close {p['symbol']} FAILED: {e}")
        st_raw.update({"halted": True, "halted_at": now_utc, "halt_reason": reason, "hwm": hwm, "last_run_utc": now_utc})
        save_json(STATE_FILE, st_raw)
        write_holdings(api, managed, now_utc, log)
        write_today(log, f"{today_et} HALTED")
        return 0

    # ------------------------------------------------------------ stale open orders
    # An unfilled order left over from an earlier run would be double-counted by the
    # reconcile below (it isn't a position yet). Cancel ours before planning.
    if not no_trade:
        try:
            for o in api.open_orders():
                if o.get("symbol") in managed:
                    api.cancel_order(o["id"])
                    log(f"cancelled stale open order {o.get('side')} {o.get('symbol')} ({o.get('status')})")
        except Exception as exc:  # noqa: BLE001
            log(f"(warn) could not check open orders ({exc})")

    # ------------------------------------------------------------ decide (once per trading day)
    positions = {p["symbol"]: p for p in api.positions()}
    current = {s: float(p.get("market_value", 0) or 0) for s, p in positions.items() if s in managed}

    bought_today = set(st_raw.get("bought_today") or []) if st_raw.get("last_decision_date") == today_et else set()
    if st_raw.get("last_decision_date") == today_et and os.path.exists(TARGETS_FILE):
        tj = load_json(TARGETS_FILE, {})
        weights = {s: float(w) for s, w in (tj.get("weights") or {}).items()}
        prices = {s: float(p.get("current_price") or 0) for s, p in positions.items()}
        try:
            prices.update(api.latest_prices(sorted(set(weights) - set(prices))))
        except Exception as exc:  # noqa: BLE001
            log(f"(data) live prices unavailable ({exc})")
        log(f"strategy already stepped today ({today_et}); re-using targets.json and reconciling only")
        fresh_decision = False
    else:
        fresh_decision = True
        symbols = sorted(managed | set(current))
        try:
            hist = load_market_history(api, symbols, today_et, log)
        except StaleData as exc:
            log(f"STALE DATA -- refusing to trade: {exc}. Snapshot only; will retry next run.")
            st_raw["last_run_utc"] = now_utc
            save_json(STATE_FILE, st_raw)
            write_holdings(api, managed, now_utc, log)
            write_today(log, f"{today_et} stale data")
            return 0
        prices = {s: v[-1] for s, v in hist.items()}
        dec = compute_targets(hist, state, params, today=today_et)
        weights = dec.weights
        for n in dec.notes:
            log(f"  strategy: {n}")
        log(f"  momentum holdings: {dec.mom_selected or '(none - defensive)'}")
        for k, v in dec.regime.items():
            log(f"  regime: {k}={v}")
        save_json(TARGETS_FILE, {
            "date": today_et, "weights": weights, "notes": dec.notes,
            "momentum": dec.mom_selected, "mean_reversion": dec.mr_open,
            "rebalanced": dec.rebalanced_momentum, "capital": capital,
            "regime": dec.regime, "preset": preset, "mode": mode,
        })
        st_raw["strategy"] = dec.state.to_dict()
        st_raw["last_decision_date"] = today_et
        st_raw["hwm"] = hwm
        st_raw["last_run_utc"] = now_utc
        save_json(STATE_FILE, st_raw)

    # ------------------------------------------------------------ news risk overlay (defensive only)
    news_cfg = cfg.get("news") or {}
    verdict = load_json(NEWS_FILE, {})
    news_log = load_json(NEWS_LOG, [])
    if fresh_decision:
        scored = news_overlay.score_previous(news_log, prices)
        if scored:
            log(f"news scorecard: override of {scored['date']} {'SAVED' if scored['effect'] >= 0 else 'COST'} "
                f"${abs(scored['effect_dollars']):,.2f} ({scored['effect']:+.2%} of capital)")
    raw_weights = dict(weights)
    weights, news_actions = news_overlay.apply(weights, verdict, today_et, news_cfg.get("scale"),
                                               enabled=bool(news_cfg.get("enabled", True)))
    if verdict.get("date") == today_et:
        log(f"news: risk level {verdict.get('market_risk')} | vetoes {[v['symbol'] for v in verdict.get('vetoes', [])]} | {verdict.get('summary', '')}")
    else:
        log("news: no verdict for today (overlay off; trading on the strategy alone)")
    for a in news_actions:
        log(f"  NEWS OVERRIDE: {a}")
    if news_actions and not any(e.get("date") == today_et for e in news_log):
        news_log.append({"date": today_et, "raw": raw_weights, "final": weights, "actions": news_actions,
                         "prices": {s: prices.get(s) for s in set(raw_weights) | set(weights) if prices.get(s)},
                         "capital": capital, "effect": None})
    if news_log:
        news_log = news_log[-500:]
        save_json(NEWS_LOG, news_log)
        sm = news_overlay.summary(news_log)
        log(f"news scorecard to date: {sm['override_days']} override days, {sm['helped']} helped / {sm['hurt']} hurt, "
            f"net {sm['net_dollars']:+,.2f}")

    # ------------------------------------------------------------ reconcile
    targets = {s: w * capital for s, w in weights.items()}
    plan = plan_orders(targets, current, min_trade, no_sell=bought_today)
    if bought_today:
        log(f"no same-day sells for {sorted(bought_today)} (bought today)")
    log("targets: " + ", ".join(f"{s} {w:.0%}" for s, w in sorted(weights.items(), key=lambda x: -x[1])) if weights else "targets: 100% cash")
    if not plan:
        log("portfolio already at target -- no orders.")
    else:
        log(f"{len(plan)} order(s):")
        asset_cache: Dict[str, dict] = {}
        fills = execute(api, plan, prices, log, no_trade, asset_cache, tag=today_et)
        for o in fills:
            if o.get("side") == "buy" or any(k == "buy" and s == o.get("symbol") for s, k, _ in plan):
                bought_today.add(str(o.get("symbol")))
    st_raw["bought_today"] = sorted(bought_today)

    if not no_trade:
        st_raw["last_trade_date"] = today_et
        if mode == "PAPER":
            st_raw["paper_clean_runs"] = int(st_raw.get("paper_clean_runs", 0) or 0) + (0 if st_raw.get("_counted_today") == today_et else 1)
            st_raw["_counted_today"] = today_et
    st_raw["last_run_utc"] = now_utc
    st_raw["hwm"] = hwm
    save_json(STATE_FILE, st_raw)
    if hasattr(api, "snapshot"):
        api.snapshot()
    snap = write_holdings(api, managed, now_utc, log)
    drift = max((abs(targets.get(s, 0.0) - float(r["market_value"])) for s, r in
                 ((r["symbol"], r) for r in snap["positions"] if r["managed"])), default=0.0)
    log(f"done: equity=${snap['equity']:,.2f} cash=${snap['cash']:,.2f} positions={[r['symbol'] for r in snap['positions']]} "
        f"max drift vs target=${drift:,.2f}")
    write_today(log, f"{today_et} {mode}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(TODAY_FILE, "a") as f:
            f.write("\n```\n" + traceback.format_exc() + "```\n")
        sys.exit(1)
