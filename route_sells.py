"""Sell router — the deterministic money-gate between the sell brain and the executor.

The SELL BRAIN (a Claude routine) writes its exit JUDGMENT to signals/proposed_sells.json:
which holdings it wants to close, a reason, and whether it's `urgent` (a thesis-shattering
catastrophe). It does NOT decide whether to ask the human — that gate is HERE, in code, so
it's reliable and not at the LLM's discretion.

Policy (user-set): the bot is HANDS-OFF / day-trader-adjacent and sells routine names on its
own. The human is asked to approve ONLY when closing a SIGNIFICANT position — one that is
long-held, a big winner, or a large share of the book (the future-AMD you don't want dumped
silently). A SIGNIFICANT position with an `urgent` (catastrophe) flag still sells immediately.

Routing for each proposed sell (looked up in the enriched holdings.json):
  * not significant            -> AUTONOMOUS  -> signals/sell_orders.json   (executor sells next run)
  * significant + urgent       -> AUTONOMOUS  -> signals/sell_orders.json   (+ FYI alert)
  * significant + routine      -> NEEDS OK    -> signals/pending_sells.json (workflow opens an approval issue)

Significance = ANY of (all tunable via env):
  * held >= LONG_HELD_DAYS                 (default 10 calendar days)
  * unrealized_pct >= TOP_GAIN_PCT         (default +25%)
  * value >= TOP_SIZE_PCT of the held book (default 20%)

Pure stdlib. Run AFTER the sell brain in sell-brain.yml: `python route_sells.py`.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

PROPOSED_FILE = "signals/proposed_sells.json"   # sell brain -> router
HOLDINGS_FILE = "signals/holdings.json"          # executor -> everyone (enriched)
SELL_ORDERS_FILE = "signals/sell_orders.json"    # router -> executor (autonomous + urgent + approved)
PENDING_FILE = "signals/pending_sells.json"      # router -> approval issue (significant + routine)

LONG_HELD_DAYS = float(os.environ.get("LONG_HELD_DAYS", "10"))
TOP_GAIN_PCT   = float(os.environ.get("TOP_GAIN_PCT", "25"))
# Size gate catches GENUINE concentration (the "AMD is half my portfolio" case), not a normal
# position in a small book — keep it high so it doesn't false-trip and break hands-off.
TOP_SIZE_PCT   = float(os.environ.get("TOP_SIZE_PCT", "35"))


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001 - missing/corrupt -> empty
        return {}


def _parse_dt(val):
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _days_held(opened_utc) -> float | None:
    dt = _parse_dt(opened_utc)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0


def classify(holding: dict, book_value: float) -> tuple[bool, list[str], float | None]:
    """Return (is_significant, reasons, days_held). A holding is significant if it's long-held,
    a big winner, or a large share of the book — the cases worth a human heads-up before
    selling. days_held is returned so callers don't recompute it."""
    reasons: list[str] = []
    days = _days_held(holding.get("opened_utc"))
    if days is not None and days >= LONG_HELD_DAYS:
        reasons.append(f"held {days:.0f}d (>= {LONG_HELD_DAYS:.0f})")
    upct = holding.get("unrealized_pct")
    if upct is not None and upct >= TOP_GAIN_PCT:
        reasons.append(f"up {upct:.0f}% (>= +{TOP_GAIN_PCT:.0f}%)")
    val = holding.get("value")
    if val and book_value > 0 and (val / book_value) * 100 >= TOP_SIZE_PCT:
        reasons.append(f"{val / book_value * 100:.0f}% of book (>= {TOP_SIZE_PCT:.0f}%)")
    return (bool(reasons), reasons, days)


def route() -> dict:
    proposed = (_load(PROPOSED_FILE).get("sells") or [])
    holdings = {str(h.get("symbol", "")).strip().upper(): h
                for h in (_load(HOLDINGS_FILE).get("holdings") or [])}
    book_value = sum((h.get("value") or 0) for h in holdings.values())
    now = datetime.now(timezone.utc).isoformat()

    autonomous: list[dict] = []   # -> sell_orders.json
    pending: list[dict] = []      # -> pending_sells.json (await approval)
    alerts: list[str] = []        # urgent significant sells (FYI)

    for p in proposed:
        sym = str(p.get("symbol", "")).strip().upper()
        if not sym or sym not in holdings:
            continue   # already sold / not held — skip
        reason = p.get("reason") or "sell brain"
        urgent = bool(p.get("urgent"))
        significant, sig_reasons, days = classify(holdings[sym], book_value)
        entry = {"symbol": sym, "reason": reason, "urgent": urgent}
        if not significant or urgent:
            autonomous.append(entry)
            if significant and urgent:
                alerts.append(f"{sym} — URGENT: {reason} ({'; '.join(sig_reasons)})")
        else:
            pending.append({**entry,
                            "significance": "; ".join(sig_reasons),
                            "unrealized_pct": holdings[sym].get("unrealized_pct"),
                            "days_held": round(days or 0, 1)})

    # Preserve already-approved sells still awaiting execution (a symbol we previously routed
    # to sell_orders that's still held) so a router re-run can't clobber a human-approved sell.
    prev = {str(s.get("symbol", "")).strip().upper(): s
            for s in (_load(SELL_ORDERS_FILE).get("sells") or [])}
    have = {e["symbol"] for e in autonomous}
    for sym, s in prev.items():
        if sym in holdings and sym not in have:
            autonomous.append(s)

    _write(SELL_ORDERS_FILE, {"generated_utc": now, "sells": autonomous})
    _write(PENDING_FILE, {"generated_utc": now, "pending": pending})
    return {"autonomous": autonomous, "pending": pending, "alerts": alerts}


def _write(path: str, data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not write {path}: {exc}")


def main() -> int:
    r = route()
    print(f"Routed sells: {len(r['autonomous'])} autonomous -> {SELL_ORDERS_FILE}, "
          f"{len(r['pending'])} awaiting approval -> {PENDING_FILE}.")
    for a in r["alerts"]:
        print(f"  ALERT (sold immediately): {a}")
    for p in r["pending"]:
        print(f"  NEEDS APPROVAL: {p['symbol']} — {p['reason']} [{p['significance']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
