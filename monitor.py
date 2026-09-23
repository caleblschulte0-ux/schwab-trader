#!/usr/bin/env python3
"""Intraday watch. Runs mid-session; NEVER trades.

History (python backtest data, SPY since 2000): after a -5% day SPY was up the next day 70%
of the time (+1.8% avg). Selling into an intraday crash tends to sell the low, so this does not.
It (1) flags a big drop in SPY/QQQ or any holding, (2) writes signals/alert.json, which the
workflow turns into a GitHub issue, and (3) asks for a forced news re-scan so the afternoon
executor run decides with fresh information.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List

import data as datamod

MARKET_DROP = float(os.environ.get("MONITOR_MARKET_DROP", "0.03"))    # SPY/QQQ down 3%+
HOLDING_DROP = float(os.environ.get("MONITOR_HOLDING_DROP", "0.06"))  # any holding down 6%+
ALERT = os.path.join("signals", "alert.json")


def prices_now(symbols: List[str]) -> Dict[str, float]:
    key, sec = os.environ.get("ALPACA_API_KEY", "").strip(), os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if key and sec:
        from alpaca import Alpaca
        return Alpaca(key, sec, paper=True).latest_prices(symbols)
    out = {}
    for s in symbols:
        try:
            bars = datamod.fetch_yahoo_daily(s, start_epoch=int(datetime.now(timezone.utc).timestamp()) - 10 * 86400)
            if bars:
                out[s] = bars[-1][1]
        except Exception:  # noqa: BLE001
            pass
    return out


def prev_closes(symbols: List[str], today: str) -> Dict[str, float]:
    out = {}
    for s in symbols:
        try:
            bars = datamod.fetch_yahoo_daily(s, start_epoch=int(datetime.now(timezone.utc).timestamp()) - 10 * 86400)
            prior = [c for d, c in bars if d < today]
            if prior:
                out[s] = prior[-1]
        except Exception:  # noqa: BLE001
            pass
    return out


def evaluate(now_px: Dict[str, float], prev: Dict[str, float], held: List[str]) -> List[str]:
    flags = []
    for s in ("SPY", "QQQ"):
        if s in now_px and s in prev and now_px[s] / prev[s] - 1 <= -MARKET_DROP:
            flags.append(f"{s} {now_px[s] / prev[s] - 1:+.1%} today")
    for s in held:
        if s in now_px and s in prev and s not in ("SPY", "QQQ") and now_px[s] / prev[s] - 1 <= -HOLDING_DROP:
            flags.append(f"holding {s} {now_px[s] / prev[s] - 1:+.1%} today")
    return flags


def main() -> int:
    from zoneinfo import ZoneInfo
    today = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    try:
        held = [p["symbol"] for p in json.load(open("signals/holdings.json")).get("positions", [])]
    except (FileNotFoundError, json.JSONDecodeError):
        held = []
    syms = sorted(set(held) | {"SPY", "QQQ"})
    flags = evaluate(prices_now(syms), prev_closes(syms, today), held)
    out = os.environ.get("GITHUB_OUTPUT")
    if flags:
        body = {"date": today, "flags": flags, "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        os.makedirs("signals", exist_ok=True)
        json.dump(body, open(ALERT, "w"), indent=2)
        print("(monitor) ALERT: " + "; ".join(flags))
    else:
        print("(monitor) nothing unusual")
    if out:
        with open(out, "a") as f:
            f.write(f"alert={'true' if flags else 'false'}\n")
            f.write(f"detail={'; '.join(flags)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
