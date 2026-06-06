"""Track-record analyzer — turns the paper book's closed trades into an EDGE read.

WHY: the system records every closed trade (paper_account.json) but never measured
whether the strategy actually makes money. Eyeballing a ledger can't answer that.
This reads the closed trades and computes the numbers that matter — win rate,
average win vs average loss, EXPECTANCY (the single number that says "edge or no
edge"), profit factor, and max drawdown — then breaks them down by SIGNAL type,
macro TAPE, catalyst FRESHNESS, exit REASON, and instrument KIND, so you learn
WHICH setups pay and which bleed. It also estimates slippage (fill vs the brain's
intended price, and fill vs last) so you can see if spread cost is eating the edge.

Reads:  signals/paper_account.json  (the `closed_trades` array bot.py maintains)
Writes: reports/track_record.md     (human scorecard)
        signals/performance.json    (compact machine read — for a future brain digest)

Pure stdlib, ZERO trading side effects, no API calls, no tokens. Trades that
predate the attribution instrumentation simply fall into an "untagged" bucket.

Run: `python analyze.py`
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

PAPER_ACCOUNT_FILE = "signals/paper_account.json"
REPORT_FILE        = "reports/track_record.md"
PERF_JSON_FILE     = "signals/performance.json"
MIN_SAMPLE         = 20   # below this, results are directional only — not conclusive


def _load_closed() -> tuple[list[dict], dict]:
    try:
        with open(PAPER_ACCOUNT_FILE, encoding="utf-8") as fh:
            book = json.load(fh)
    except Exception:  # noqa: BLE001
        return [], {}
    return (book.get("closed_trades") or []), book


def _stats(trades: list[dict]) -> dict:
    """Core metrics for a set of trades (P/L in $ is the real money; pnl_pct is the
    per-trade % for reference). Expectancy = average $ P/L per trade — the headline."""
    n = len(trades)
    if not n:
        return {"n": 0, "win_rate": 0.0, "total": 0.0, "expectancy": 0.0,
                "avg_win": 0.0, "avg_loss": 0.0, "payoff": 0.0, "profit_factor": 0.0,
                "avg_pct": 0.0}
    pnls = [t.get("pnl", 0.0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)  # positive magnitude
    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0   # negative
    pcts = [t.get("pnl_pct", 0.0) for t in trades if t.get("pnl_pct") is not None]
    return {
        "n": n,
        "win_rate": 100.0 * len(wins) / n,
        "total": sum(pnls),
        "expectancy": sum(pnls) / n,                       # avg $ per trade
        "avg_win": avg_win,
        "avg_loss": avg_loss,                              # negative number
        "payoff": (avg_win / abs(avg_loss)) if avg_loss else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss else float("inf") if gross_win else 0.0,
        "avg_pct": (sum(pcts) / len(pcts)) if pcts else 0.0,
    }


def _max_drawdown(trades: list[dict]) -> float:
    """Worst peak-to-trough drop of the REALIZED cumulative P/L curve (closed trades
    in time order). Realized-only — it does not include open mark-to-market."""
    ordered = sorted(trades, key=lambda t: str(t.get("closed_utc") or ""))
    cum = peak = 0.0
    max_dd = 0.0
    for t in ordered:
        cum += t.get("pnl", 0.0)
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)
    return max_dd   # <= 0


def _freshness_bucket(t: dict) -> str:
    age = t.get("catalyst_age_h")
    if age is None:
        return "no-catalyst/untagged"
    if age < 2:
        return "<2h (fresh)"
    if age < 12:
        return "2-12h"
    if age < 48:
        return "12-48h"
    return ">48h (stale)"


def _exit_bucket(t: dict) -> str:
    why = str(t.get("reason", "")).lower()
    if "target" in why:
        return "hit target"
    if "stop" in why:
        return "hit stop"
    if "brain" in why:
        return "brain SELL"
    return why or "other"


def _group(trades: list[dict], key_fn) -> dict[str, dict]:
    """Group trades by key_fn (which may return a LIST to put a trade in several
    buckets, e.g. a trade tagged both 'mover' and 'news_smallcap')."""
    buckets: dict[str, list] = {}
    for t in trades:
        keys = key_fn(t)
        if not isinstance(keys, (list, tuple, set)):
            keys = [keys]
        for k in (keys or ["untagged"]):
            buckets.setdefault(str(k), []).append(t)
    return {k: _stats(v) for k, v in buckets.items()}


def _slippage(trades: list[dict]) -> dict:
    """Average entry slippage. vs_ref = fill above the brain's intended price;
    vs_last = fill above the last trade (a spread-cost proxy). Stocks only (option
    premiums distort the %). Only trades carrying the fields count."""
    ref_sl, last_sl = [], []
    for t in trades:
        if t.get("kind", "stock") != "stock":
            continue
        entry = t.get("entry")
        ref = t.get("ref_price")
        last = t.get("entry_last")
        if entry and ref:
            ref_sl.append((entry / ref - 1) * 100)
        if entry and last:
            last_sl.append((entry / last - 1) * 100)
    return {
        "vs_ref_pct": (sum(ref_sl) / len(ref_sl)) if ref_sl else None,
        "vs_ref_n": len(ref_sl),
        "vs_last_pct": (sum(last_sl) / len(last_sl)) if last_sl else None,
        "vs_last_n": len(last_sl),
    }


def _fmt_group(title: str, groups: dict[str, dict]) -> list[str]:
    if not groups:
        return [f"### {title}", "", "_no data_", ""]
    rows = ["### " + title, "",
            "| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |",
            "|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|"]
    for name, s in sorted(groups.items(), key=lambda kv: kv[1]["total"], reverse=True):
        pf = "∞" if s["profit_factor"] == float("inf") else f"{s['profit_factor']:.2f}"
        rows.append(f"| {name} | {s['n']} | {s['win_rate']:.0f}% | ${s['total']:+.2f} | "
                    f"${s['expectancy']:+.2f} | ${s['avg_win']:+.2f} | ${s['avg_loss']:+.2f} | {pf} |")
    rows.append("")
    return rows


def build_report(trades: list[dict], book: dict) -> tuple[str, dict]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    overall = _stats(trades)
    dd = _max_drawdown(trades)
    slip = _slippage(trades)
    n = overall["n"]

    verdict = "NO EDGE YET" if n == 0 else (
        "POSITIVE EXPECTANCY ✅" if overall["expectancy"] > 0 else "NEGATIVE EXPECTANCY ❌")
    pf = "∞" if overall["profit_factor"] == float("inf") else f"{overall['profit_factor']:.2f}"

    lines = [
        "# Track Record — Edge Analysis", "",
        f"_Updated {now} · source: {PAPER_ACCOUNT_FILE} (paper / DRY_RUN)_", "",
    ]
    if n < MIN_SAMPLE:
        lines += [f"> ⚠️ **SAMPLE TOO SMALL ({n} closed trades, need ≥{MIN_SAMPLE}).** "
                  "Everything below is DIRECTIONAL ONLY — not statistically conclusive. "
                  "Do not change strategy parameters or go live off this. Let it gather a "
                  "clean sample first.", ""]
    lines += [
        "## Headline", "",
        f"**Verdict: {verdict}**  ",
        f"**Closed trades:** {n}   **Win rate:** {overall['win_rate']:.0f}%   "
        f"**Total realized:** ${overall['total']:+.2f}  ",
        f"**Expectancy (avg $/trade):** ${overall['expectancy']:+.2f}   "
        f"**Avg %/trade:** {overall['avg_pct']:+.2f}%  ",
        f"**Avg win:** ${overall['avg_win']:+.2f}   **Avg loss:** ${overall['avg_loss']:+.2f}   "
        f"**Payoff ratio:** {overall['payoff']:.2f}   **Profit factor:** {pf}  ",
        f"**Max drawdown (realized):** ${dd:+.2f}", "",
    ]
    # Slippage
    lines += ["## Entry slippage (stocks)", ""]
    if slip["vs_ref_pct"] is None and slip["vs_last_pct"] is None:
        lines += ["_no attributed entries yet (pre-instrumentation trades)_", ""]
    else:
        if slip["vs_ref_pct"] is not None:
            lines.append(f"- **Fill vs brain's intended price:** {slip['vs_ref_pct']:+.2f}% "
                         f"(n={slip['vs_ref_n']}) — how much above the brain's limit we actually paid.")
        if slip["vs_last_pct"] is not None:
            lines.append(f"- **Fill vs last trade (spread proxy):** {slip['vs_last_pct']:+.2f}% "
                         f"(n={slip['vs_last_n']}) — paid spread on entry. Doubles round-trip; "
                         "compare to your ~5–10% targets.")
        lines.append("")

    # Breakdowns
    lines += ["## Breakdowns", ""]
    lines += _fmt_group("By signal", _group(trades, lambda t: t.get("signals") or ["untagged"]))
    lines += _fmt_group("By macro tape at entry", _group(trades, lambda t: t.get("tape_tone") or "untagged"))
    lines += _fmt_group("By catalyst freshness", _group(trades, _freshness_bucket))
    lines += _fmt_group("By exit reason", _group(trades, _exit_bucket))
    lines += _fmt_group("By kind", _group(trades, lambda t: t.get("kind", "stock")))

    # Compact machine read for a future brain digest (Form 1 of the learning loop).
    perf = {
        "updated_utc": now,
        "n": n,
        "expectancy": round(overall["expectancy"], 4),
        "win_rate": round(overall["win_rate"], 1),
        "total_realized": round(overall["total"], 2),
        "profit_factor": (None if overall["profit_factor"] == float("inf")
                          else round(overall["profit_factor"], 3)),
        "max_drawdown": round(dd, 2),
        "by_signal": {k: {"n": v["n"], "win_rate": round(v["win_rate"], 1),
                          "expectancy": round(v["expectancy"], 4)}
                      for k, v in _group(trades, lambda t: t.get("signals") or ["untagged"]).items()},
        "sample_sufficient": n >= MIN_SAMPLE,
    }
    return "\n".join(lines) + "\n", perf


def main() -> int:
    trades, book = _load_closed()
    report, perf = build_report(trades, book)
    for path, content in ((REPORT_FILE, report),
                          (PERF_JSON_FILE, json.dumps(perf, indent=2) + "\n")):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except Exception as exc:  # noqa: BLE001
            print(f"(warn) could not write {path}: {exc}")
    print(f"Analyzed {perf['n']} closed trades → expectancy ${perf['expectancy']:+.4f}/trade, "
          f"win rate {perf['win_rate']:.0f}%. Wrote {REPORT_FILE} + {PERF_JSON_FILE}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
