"""Day-trade executor — entries + exits, dry-run by default.

Pipeline: a scheduled Claude routine (the "brain") researches the market and
writes picks to `signals/orders.json`. This bot, run every 30 min by GitHub
Actions, reads them, RE-CHECKS every guardrail in code, and manages a full
day-trade lifecycle:

  ENTRIES  buy a DAY limit (buy-only, <= $65, skip if already held). DAY orders
           expire at the close, so nothing unfilled lingers overnight.

  EXITS    (all SELL-to-close — we only ever sell what we already own, never short)
    1. Profit target / stop: each run, compare live price to entry; sell at
       +TAKE_PROFIT_PCT or -STOP_LOSS_PCT.
    2. Brain exit: a {"action":"SELL"} entry in orders.json for a held symbol
       closes it.
    3. End-of-day flatten: on the run shortly before the close, sell everything
       still open so the day ends flat (true day trading).

SAFETY: DRY_RUN defaults to "true" — it only logs "would buy/sell" and places
nothing until a DRY_RUN repo variable is set to "false". Buy-to-open only;
sell only to close a held long. Quantities are clamped to what is actually held.

Secrets (GitHub Actions): SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_REFRESH_TOKEN
Optional: SCHWAB_CALLBACK_URL, DRY_RUN
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from schwab import SchwabAuth, SchwabClient
from schwab.models.generated.trading_models import Instruction, Duration

# ===== GUARDRAILS / KNOBS (enforced here no matter what the brain says) =====
MAX_DOLLARS_PER_TRADE = 65.00   # never spend more than this on one entry
TAKE_PROFIT_PCT       = 0.08    # sell a winner at +8%
STOP_LOSS_PCT         = 0.05    # sell a loser at -5%
MAX_SIGNAL_AGE_HOURS  = 18      # ignore a stale orders.json
# Flatten window (UTC). US close = 20:00 UTC; we flatten on the ~19:30 run.
FLATTEN_AFTER_UTC_MIN = 19 * 60 + 25   # 19:25 UTC  (~2:25 PM CDT)
ORDERS_FILE           = "signals/orders.json"
# ===========================================================================

APP_KEY       = os.environ["SCHWAB_APP_KEY"].strip()
APP_SECRET    = os.environ["SCHWAB_APP_SECRET"].strip()
REFRESH_TOKEN = os.environ["SCHWAB_REFRESH_TOKEN"].strip()
CALLBACK      = os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1/").strip()
DRY_RUN       = os.environ.get("DRY_RUN", "true").strip().lower() != "false"


def get_client() -> SchwabClient:
    auth = SchwabAuth(APP_KEY, APP_SECRET, CALLBACK)
    auth.refresh_token = REFRESH_TOKEN
    try:
        auth.refresh_access_token()
    except Exception as exc:  # noqa: BLE001
        resp = getattr(exc, "response", None)
        if resp is not None:
            print(f"Schwab token endpoint said: HTTP {resp.status_code} -> {resp.text}")
        raise
    return SchwabClient(APP_KEY, APP_SECRET, CALLBACK, auth=auth)


def load_orders() -> tuple[str | None, list[dict]]:
    if not os.path.exists(ORDERS_FILE):
        print(f"No {ORDERS_FILE} found.")
        return None, []
    with open(ORDERS_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("generated_utc"), data.get("orders", []) or []


def is_fresh(generated_utc: str | None) -> bool:
    if not generated_utc:
        return True
    try:
        ts = datetime.fromisoformat(generated_utc.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    print(f"Signal generated {generated_utc} ({age_h:.1f}h ago; max {MAX_SIGNAL_AGE_HOURS}h)")
    return age_h <= MAX_SIGNAL_AGE_HOURS


def in_flatten_window() -> bool:
    now = datetime.now(timezone.utc)
    return (now.hour * 60 + now.minute) >= FLATTEN_AFTER_UTC_MIN


def get_positions(client: SchwabClient) -> dict[str, dict]:
    """{symbol: {"qty": longQty, "avg": averagePrice}} for held longs."""
    out: dict[str, dict] = {}
    try:
        for acct in client.get_accounts(include_positions=True):
            sec = getattr(acct, "securities_account", None)
            d = sec.model_dump() if hasattr(sec, "model_dump") else (sec or {})
            for p in (d.get("positions") or []):
                pd = p.model_dump() if hasattr(p, "model_dump") else (p or {})
                instr = pd.get("instrument") or {}
                sym = instr.get("symbol") if isinstance(instr, dict) else None
                qty = pd.get("longQuantity") or 0
                if sym and qty > 0:
                    out[sym] = {"qty": qty, "avg": pd.get("averagePrice") or 0}
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not read positions: {exc}")
    return out


def last_price(client: SchwabClient, symbol: str) -> float | None:
    try:
        q = client.get_quotes(symbol)
        d = q.model_dump() if hasattr(q, "model_dump") else dict(q)
        found: dict[str, float] = {}

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, (int, float)):
                        found.setdefault(k.lower(), float(v))
                    walk(v)
            elif isinstance(o, list):
                for x in o:
                    walk(x)

        walk(d)
        for key in ("lastprice", "last_price", "mark", "bidprice", "bid_price"):
            if key in found:
                return found[key]
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) no quote for {symbol}: {exc}")
    return None


def sell_to_close(client, acct, symbol: str, qty, limit: float, why: str):
    """Place a SELL limit to close a held long (or log it in dry-run)."""
    qty = int(qty)
    if qty <= 0:
        return
    if DRY_RUN:
        print(f"[{symbol}] DRY-RUN: would SELL {qty} @ ${limit:.2f} to close ({why})")
        return
    try:
        order = client.create_limit_order(
            symbol=symbol, quantity=qty, limit_price=round(limit, 2),
            instruction=Instruction.sell, duration=Duration.day,
        )
        client.place_order(acct.hash_value, order)
        print(f"[{symbol}] ✅ LIVE SELL {qty} @ ${limit:.2f} to close ({why})")
    except Exception as exc:  # noqa: BLE001
        print(f"[{symbol}] sell error: {exc}")


def buy_entry(client, acct, symbol: str, qty: int, limit: float):
    if DRY_RUN:
        print(f"[{symbol}] DRY-RUN: would BUY {qty} @ ${limit:.2f} = ${qty * limit:.2f}")
        return
    try:
        order = client.create_limit_order(
            symbol=symbol, quantity=qty, limit_price=round(limit, 2),
            instruction=Instruction.buy, duration=Duration.day,
        )
        client.place_order(acct.hash_value, order)
        print(f"[{symbol}] ✅ LIVE BUY {qty} @ ${limit:.2f}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{symbol}] buy error: {exc}")


def manage_exits(client, acct, positions: dict, brain_sells: set[str]):
    """Sell-to-close on target/stop or when the brain says to."""
    for sym, pos in positions.items():
        price = last_price(client, sym)
        if price is None:
            continue
        avg = pos["avg"] or price
        change = (price - avg) / avg if avg else 0
        if sym in brain_sells:
            sell_to_close(client, acct, sym, pos["qty"], price, "brain SELL signal")
        elif change >= TAKE_PROFIT_PCT:
            sell_to_close(client, acct, sym, pos["qty"], price, f"+{change*100:.1f}% target")
        elif change <= -STOP_LOSS_PCT:
            sell_to_close(client, acct, sym, pos["qty"], price, f"{change*100:.1f}% stop")
        else:
            print(f"[{sym}] hold — {change*100:+.1f}% vs entry (target +{TAKE_PROFIT_PCT*100:.0f}% / stop -{STOP_LOSS_PCT*100:.0f}%)")


def flatten_all(client, acct, positions: dict):
    print("--- END-OF-DAY FLATTEN: closing all open positions ---")
    if not positions:
        print("Already flat — nothing to close.")
        return
    for sym, pos in positions.items():
        price = last_price(client, sym) or pos["avg"]
        sell_to_close(client, acct, sym, pos["qty"], price, "EOD flatten")


def passes_entry_guardrails(order: dict) -> tuple[bool, str]:
    if order.get("action") != "BUY":
        return False, "not a BUY"
    if order.get("instrument", "stock") != "stock":
        return False, "only stocks supported for now"
    qty = order.get("quantity") or 0
    limit = order.get("limit_price") or 0
    if qty <= 0 or limit <= 0:
        return False, "bad quantity/limit_price"
    if qty * limit > MAX_DOLLARS_PER_TRADE:
        return False, f"${qty*limit:.2f} exceeds ${MAX_DOLLARS_PER_TRADE:.0f} cap"
    return True, "ok"


def main() -> int:
    mode = "DRY-RUN (no real orders)" if DRY_RUN else "LIVE (real orders!)"
    print(f"=== Day-trade executor | mode: {mode} ===")

    client = get_client()
    acct = client.get_account_numbers().accounts[0]
    positions = get_positions(client)
    print(f"Open positions: {', '.join(positions) if positions else '(none)'}")

    # 1. End-of-day: flatten everything and stop (no new entries near the close).
    if in_flatten_window():
        flatten_all(client, acct, positions)
        print("=== done (flatten) ===")
        return 0

    # 2. Load the brain's picks.
    generated_utc, orders = load_orders()
    fresh = orders and is_fresh(generated_utc)
    brain_sells = {o.get("symbol") for o in orders if o.get("action") == "SELL"} if fresh else set()

    # 3. Manage exits on anything we hold (target / stop / brain signal).
    manage_exits(client, acct, positions, brain_sells)

    # 4. Open new entries from fresh BUY picks.
    if not fresh:
        print("No fresh BUY picks to act on.")
        print("=== done ===")
        return 0

    for order in orders:
        if order.get("action") != "BUY":
            continue
        sym = order.get("symbol", "?")
        ok, why = passes_entry_guardrails(order)
        if not ok:
            print(f"[{sym}] SKIP entry — {why}")
            continue
        if sym in positions:
            print(f"[{sym}] SKIP entry — already holding")
            continue
        buy_entry(client, acct, sym, int(order["quantity"]), float(order["limit_price"]))

    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
