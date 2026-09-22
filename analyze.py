#!/usr/bin/env python3
"""Track record from the broker's own books (not a home-grown ledger).

Reads the Alpaca portfolio-history equity curve and every FILL, pairs fills into
round-trip trades (FIFO per symbol), and writes:
  reports/track_record.md   equity stats + trade stats + the strategy backtest for reference
  reports/paper_ledger.md   recent equity curve + open positions
  signals/performance.json  machine-readable summary
Never fails the trading run: any error is printed and exit code stays 0.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List

from alpaca import Alpaca

PERIOD = os.environ.get("TRACK_PERIOD", "1A")


def env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return default if not v else v in ("1", "true", "yes", "on")


def equity_stats(ts: List[int], eq: List[float]) -> dict:
    pts = [(t, e) for t, e in zip(ts, eq) if e is not None and e > 0]
    if len(pts) < 2:
        return {}
    eqs = [e for _, e in pts]
    rets = [eqs[i] / eqs[i - 1] - 1 for i in range(1, len(eqs))]
    m = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / max(1, len(rets) - 1))
    peak = eqs[0]
    mdd = 0.0
    for e in eqs:
        peak = max(peak, e)
        mdd = min(mdd, e / peak - 1)
    days = max(1, (pts[-1][0] - pts[0][0]) / 86400)
    total = eqs[-1] / eqs[0] - 1
    cagr = (eqs[-1] / eqs[0]) ** (365.0 / days) - 1 if days >= 30 else None
    return {
        "start": datetime.fromtimestamp(pts[0][0], tz=timezone.utc).strftime("%Y-%m-%d"),
        "end": datetime.fromtimestamp(pts[-1][0], tz=timezone.utc).strftime("%Y-%m-%d"),
        "start_equity": eqs[0], "end_equity": eqs[-1], "total_return": total, "cagr": cagr,
        "sharpe": (m / sd * math.sqrt(252)) if sd > 0 else 0.0,
        "max_drawdown": mdd, "days": int(days), "n_points": len(eqs),
        "curve": [(datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"), e) for t, e in pts],
    }


def round_trips(fills: List[dict]) -> List[dict]:
    """FIFO-pair buys and sells per symbol into closed trades."""
    lots: Dict[str, List[List[float]]] = {}  # sym -> [[qty, price, ts]]
    trades: List[dict] = []
    for f in sorted(fills, key=lambda x: x.get("transaction_time", "")):
        sym = f.get("symbol")
        qty = float(f.get("qty", 0) or 0)
        px = float(f.get("price", 0) or 0)
        side = f.get("side")
        ts = f.get("transaction_time", "")
        if not sym or qty <= 0 or px <= 0:
            continue
        if side == "buy":
            lots.setdefault(sym, []).append([qty, px, ts])
        elif side in ("sell", "sell_short"):
            remaining = qty
            while remaining > 1e-9 and lots.get(sym):
                lot = lots[sym][0]
                take = min(lot[0], remaining)
                pnl = (px - lot[1]) * take
                trades.append({"symbol": sym, "qty": take, "entry": lot[1], "exit": px,
                               "pnl": round(pnl, 2), "pnl_pct": round((px / lot[1] - 1) * 100, 2),
                               "opened": lot[2], "closed": ts})
                lot[0] -= take
                remaining -= take
                if lot[0] <= 1e-9:
                    lots[sym].pop(0)
    return trades


def trade_stats(trades: List[dict]) -> dict:
    if not trades:
        return {"n": 0}
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gp = sum(t["pnl"] for t in wins)
    gl = -sum(t["pnl"] for t in losses)
    return {
        "n": len(trades), "win_rate": len(wins) / len(trades),
        "total_pnl": round(sum(t["pnl"] for t in trades), 2),
        "expectancy": round(sum(t["pnl"] for t in trades) / len(trades), 2),
        "avg_win": round(gp / len(wins), 2) if wins else 0.0,
        "avg_loss": round(-gl / len(losses), 2) if losses else 0.0,
        "profit_factor": round(gp / gl, 2) if gl > 0 else None,
    }


def main() -> int:
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if not key or not secret:
        print("(analyze) no Alpaca credentials; skipping")
        return 0
    api = Alpaca(key, secret, paper=env_bool("DRY_RUN", True))
    mode = "paper" if api.paper else "LIVE"

    hist = api.portfolio_history(period=PERIOD, timeframe="1D")
    es = equity_stats(hist.get("timestamp") or [], hist.get("equity") or [])
    fills = api.fills(after="2000-01-01")
    trades = round_trips(fills)
    ts = trade_stats(trades)
    positions = api.positions()
    acct = api.account()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    os.makedirs("reports", exist_ok=True)
    os.makedirs("signals", exist_ok=True)
    L = [f"# Track Record ({mode})", "", f"_Updated {now} · source: Alpaca account history_", ""]
    if es:
        cagr_txt = f"{es['cagr']:+.1%}" if es["cagr"] is not None else "n/a (<30d)"
        L += ["## Equity", "",
              f"| Since | Start | Now | Total | CAGR | Sharpe | Max DD |", "|---|---:|---:|---:|---:|---:|---:|",
              f"| {es['start']} | ${es['start_equity']:,.2f} | ${es['end_equity']:,.2f} | {es['total_return']:+.2%} | "
              f"{cagr_txt} | {es['sharpe']:.2f} | {es['max_drawdown']:.1%} |", ""]
    else:
        L += ["_No equity history yet._", ""]
    L += ["## Closed trades (FIFO round-trips from broker fills)", ""]
    if ts.get("n"):
        L += [f"**{ts['n']} trades · win rate {ts['win_rate']:.0%} · total {ts['total_pnl']:+,.2f} · expectancy {ts['expectancy']:+,.2f}/trade · "
              f"avg win {ts['avg_win']:+,.2f} · avg loss {ts['avg_loss']:+,.2f} · profit factor {ts['profit_factor']}**", "",
              "| Symbol | Qty | Entry | Exit | P&L | % | Opened | Closed |", "|---|---:|---:|---:|---:|---:|---|---|"]
        for t in trades[-40:]:
            L.append(f"| {t['symbol']} | {t['qty']:g} | {t['entry']:.2f} | {t['exit']:.2f} | {t['pnl']:+.2f} | {t['pnl_pct']:+.2f}% | {t['opened'][:10]} | {t['closed'][:10]} |")
        L.append("")
        if ts["n"] < 30:
            L.append("> Small sample: with fewer than ~30 closed trades these numbers are directional only.")
    else:
        L += ["_No closed trades yet._"]
    L += ["", "## Reference: strategy backtest", "", "See `reports/backtest.md` (18 years of daily data, same code path as the live bot)."]
    with open("reports/track_record.md", "w") as f:
        f.write("\n".join(L) + "\n")

    P = [f"# Ledger ({mode})", "", f"_Updated {now}_", "",
         f"**Equity ${float(acct.get('equity', 0)):,.2f} · cash ${float(acct.get('cash', 0)):,.2f}**", "",
         "## Open positions", "", "| Symbol | Qty | Avg entry | Last | Value | Unrealized |", "|---|---:|---:|---:|---:|---:|"]
    for p in sorted(positions, key=lambda x: -float(x.get("market_value", 0) or 0)):
        P.append(f"| {p['symbol']} | {float(p['qty']):g} | {float(p['avg_entry_price']):.2f} | {float(p.get('current_price') or 0):.2f} | "
                 f"${float(p.get('market_value') or 0):,.2f} | {float(p.get('unrealized_plpc') or 0):+.2%} |")
    if not positions:
        P.append("| (none) | | | | | |")
    if es:
        P += ["", "## Equity curve (last 30 points)", "", "| Date | Equity |", "|---|---:|"]
        for d, e in es["curve"][-30:]:
            P.append(f"| {d} | ${e:,.2f} |")
    with open("reports/paper_ledger.md", "w") as f:
        f.write("\n".join(P) + "\n")

    perf = {"updated_utc": now, "mode": mode, "equity": {k: v for k, v in es.items() if k != "curve"}, "trades": ts}
    with open("signals/performance.json", "w") as f:
        json.dump(perf, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"(analyze) {mode}: equity ${float(acct.get('equity', 0)):,.2f}, {ts.get('n', 0)} closed trades -> reports/track_record.md")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"(analyze) failed: {exc}")
        sys.exit(0)
