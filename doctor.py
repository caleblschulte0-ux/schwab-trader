#!/usr/bin/env python3
"""Preflight: is this deployment healthy? Prints a checklist; exit 1 only with --strict.

    python doctor.py            # human-readable
    python doctor.py --strict   # non-zero exit on any FAIL (used by CI)
    python doctor.py --probe    # PAPER keys only: sweep every endpoint the bot uses and do a
                                # $1 SPY buy -> close round trip, so the real API contract is
                                # verified before any live order is ever placed.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

OK, WARN, FAIL = "OK  ", "WARN", "FAIL"
rows = []


def check(name: str, status: str, detail: str = "") -> None:
    rows.append((status, name, detail))


def main() -> int:
    strict = "--strict" in sys.argv
    # --- python & imports
    check("python >= 3.11", OK if sys.version_info >= (3, 11) else FAIL, sys.version.split()[0])
    try:
        import strategy, backtest, alpaca, broker_sim, config as cfgmod, data as datamod  # noqa: F401
        check("imports", OK)
    except Exception as exc:  # noqa: BLE001
        check("imports", FAIL, str(exc))
        return _report(strict)
    # --- config
    try:
        cfg = cfgmod.load_config()
        params, preset = cfgmod.build_params(cfg)
        ex = cfgmod.executor_settings(cfg)
        check("config.json", OK, f"preset={preset} top_n={params.mom_top_n} rebalance={params.mom_rebalance_days}d "
                                  f"core={params.core_weight:.0%} {params.core_symbol} cluster_cap={params.cluster_cap} "
                                  f"halt={ex['max_drawdown_halt']:.0%} window={ex['trade_window_min']:.0f}m")
    except Exception as exc:  # noqa: BLE001
        check("config.json", FAIL, str(exc))
    # --- credentials / broker
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    sec = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if key and sec:
        try:
            api = alpaca.Alpaca(key, sec, paper=os.environ.get("DRY_RUN", "true").lower() != "false")
            a = api.account()
            c = api.clock()
            check("alpaca account", OK if not a.get("trading_blocked") else FAIL,
                  f"{'paper' if api.paper else 'LIVE'} status={a.get('status')} equity=${float(a.get('equity', 0)):,.2f} "
                  f"market_open={c.get('is_open')} next_close={c.get('next_close')}")
            bars = api.daily_bars(["SPY"], start=(datetime.now(timezone.utc).strftime("%Y-01-01")))
            check("alpaca data", OK if len(bars.get("SPY", [])) > 50 else WARN, f"{len(bars.get('SPY', []))} SPY bars this year")
        except Exception as exc:  # noqa: BLE001
            check("alpaca", FAIL, str(exc)[:200])
        if "--probe" in sys.argv:
            _probe(api)
        # live-readiness gate (same function the executor uses)
        try:
            import bot as botmod
            st = json.load(open("signals/state.json")) if os.path.exists("signals/state.json") else {}
            reasons = botmod.live_gate(ex, st)
            check("live readiness", OK if not reasons else WARN,
                  "all gates satisfied -- LIVE would be accepted" if not reasons else "; ".join(reasons))
        except Exception as exc:  # noqa: BLE001
            check("live readiness", WARN, str(exc)[:120])
    else:
        check("alpaca keys", WARN, "not set: bot trades the built-in simulator (fine for now; see SETUP.md)")
    # --- market data fallback
    try:
        t0 = time.time()
        bars = datamod.fetch_yahoo_daily("SPY", start_epoch=int(time.time()) - 400 * 86400)
        check("yahoo data", OK if len(bars) > 200 else WARN, f"{len(bars)} bars, latest {bars[-1][0]} ({time.time() - t0:.1f}s)")
    except Exception as exc:  # noqa: BLE001
        check("yahoo data", FAIL, str(exc)[:200])
    # --- state
    try:
        with open("signals/state.json") as f:
            st = json.load(f)
        age_h = None
        if st.get("last_run_utc"):
            age_h = (datetime.now(timezone.utc) - datetime.strptime(st["last_run_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 3600
        check("state.json", FAIL if st.get("halted") else (WARN if age_h and age_h > 80 else OK),
              (f"HALTED: {st.get('halt_reason')}" if st.get("halted") else f"last run {age_h:.0f}h ago, last trade {st.get('last_trade_date')}, hwm ${st.get('hwm', 0):,.2f}" if age_h is not None else "never run"))
    except FileNotFoundError:
        check("state.json", WARN, "no runs yet")
    # --- tests
    try:
        import subprocess
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], capture_output=True, text=True, timeout=300)
        last = (r.stderr.strip().splitlines() or ["?"])[-1]
        check("unit tests", OK if r.returncode == 0 else FAIL, last)
    except Exception as exc:  # noqa: BLE001
        check("unit tests", WARN, str(exc)[:100])
    return _report(strict)


def _probe(api) -> None:
    """Exercise the real API surface on the PAPER account. Never runs against live."""
    if not api.paper:
        check("probe", FAIL, "refusing to probe a LIVE account")
        return
    try:
        cal = api.calendar(datetime.now(timezone.utc).strftime("%Y-%m-%d"), datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        pos = api.positions()
        opn = api.open_orders()
        a = api.asset("SPY")
        px = api.latest_prices(["SPY", "BIL", "GLD"])
        bars = api.daily_bars(["SPY", "BIL"], start=(datetime.now(timezone.utc).strftime("%Y-01-01")))
        hist = api.portfolio_history(period="1M", timeframe="1D")
        fills = api.fills(after="2000-01-01")
        flows = api.cash_flows(after="2000-01-01")
        check("probe: reads", OK, f"calendar={len(cal)} positions={len(pos)} open_orders={len(opn)} SPY fractionable={a.get('fractionable')} "
                                  f"prices={len(px)} bars(SPY)={len(bars.get('SPY', []))} history_pts={len(hist.get('equity') or [])} "
                                  f"fills={len(fills)} net_flows={flows:+.2f}")
    except Exception as exc:  # noqa: BLE001
        check("probe: reads", FAIL, str(exc)[:200])
        return
    try:
        clock = api.clock()
        if not clock.get("is_open"):
            check("probe: order round-trip", WARN, "market closed; skipped the $1 SPY buy/close (run during market hours)")
            return
        o = api.submit_order("SPY", "buy", notional=1.0, client_order_id=f"probe-{int(time.time())}")
        o = api.wait_for_fill(o["id"], timeout_s=60)
        if o.get("status") != "filled":
            check("probe: order round-trip", FAIL, f"buy status {o.get('status')}")
            return
        qty = float(o.get("filled_qty") or 0)
        c = api.submit_order("SPY", "sell", qty=qty, client_order_id=f"probe-close-{int(time.time())}")
        c = api.wait_for_fill(c["id"], timeout_s=60)
        check("probe: order round-trip", OK if c.get("status") == "filled" else WARN,
              f"bought {qty:g} SPY @ {o.get('filled_avg_price')}, sold @ {c.get('filled_avg_price')} ({c.get('status')})")
    except Exception as exc:  # noqa: BLE001
        check("probe: order round-trip", FAIL, str(exc)[:200])


def _report(strict: bool) -> int:
    print(f"doctor @ {datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z")
    for status, name, detail in rows:
        print(f"  [{status}] {name:<16} {detail}")
    fails = [r for r in rows if r[0] == FAIL]
    print(f"  => {len(fails)} FAIL, {sum(1 for r in rows if r[0] == WARN)} WARN")
    return 1 if (strict and fails) else 0


if __name__ == "__main__":
    sys.exit(main())
