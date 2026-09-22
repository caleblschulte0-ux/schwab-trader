#!/usr/bin/env python3
"""Preflight: is this deployment healthy? Prints a checklist; exit 1 only with --strict.

    python doctor.py            # human-readable
    python doctor.py --strict   # non-zero exit on any FAIL (used by CI)
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


def _report(strict: bool) -> int:
    print(f"doctor @ {datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z")
    for status, name, detail in rows:
        print(f"  [{status}] {name:<16} {detail}")
    fails = [r for r in rows if r[0] == FAIL]
    print(f"  => {len(fails)} FAIL, {sum(1 for r in rows if r[0] == WARN)} WARN")
    return 1 if (strict and fails) else 0


if __name__ == "__main__":
    sys.exit(main())
