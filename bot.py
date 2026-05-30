"""Swing/day-trade executor — bracket entries + brain-set exits, dry-run by default.

Pipeline: a scheduled Claude routine (the "brain") researches the market and
writes picks to `signals/orders.json`. This bot, run every 30 min by GitHub
Actions, reads them, RE-CHECKS every guardrail in code, and manages positions.

ENTRIES — for each fresh BUY pick:
  Place a BRACKET order: a GTC limit buy with the brain's take-profit and
  stop-loss attached as resting child orders. The exits live ON THE EXCHANGE,
  so they fire automatically whenever price hits the target/stop — even when
  this bot isn't running and even after hours. We do NOT force-sell at the
  close; winners can ride / hold overnight.
  Guardrails (enforced here regardless of what the brain wrote):
    * BUY-only, stocks only, quantity * limit <= MAX_DOLLARS_PER_TRADE
    * skip symbols already HELD or with a WORKING/PENDING order (no double-buys)
    * the brain MUST supply take_profit and stop_loss prices, and they must be
      sane (stop < entry < target) or the entry is skipped.

EXITS — three layers, all SELL-to-close (we only sell shares we own, never short):
  1. The bracket's resting target/stop (primary; works while bot is offline).
  2. Brain SELL signal: {"action":"SELL"} for a held symbol -> close it now.
  (No end-of-day flatten — positions may be held overnight by design.)

SAFETY: DRY_RUN defaults to "true" — only logs "would buy/sell", places nothing,
until a DRY_RUN repo variable is set to "false".

Secrets (GitHub Actions): SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_REFRESH_TOKEN
Optional: SCHWAB_CALLBACK_URL, DRY_RUN
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from schwab import SchwabAuth, SchwabClient
from schwab.models.generated.trading_models import Instruction, Duration, OrderType

# ===== GUARDRAILS / KNOBS =====
MAX_DOLLARS_PER_TRADE = 65.00   # never spend more than this on one entry
MAX_SIGNAL_AGE_HOURS  = 18      # ignore a stale orders.json
ORDERS_FILE           = "signals/orders.json"
# Win/loss levels are NOT fixed here — the brain sets take_profit & stop_loss
# per pick. These bounds only reject obviously-broken values.
MIN_TP_OVER_ENTRY     = 0.005   # target must be >= 0.5% above entry
MIN_STOP_UNDER_ENTRY  = 0.005   # stop must be >= 0.5% below entry
# ==============================

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


def _as_dict(o):
    if o is None:
        return {}
    if hasattr(o, "model_dump"):
        return o.model_dump()
    if isinstance(o, dict):
        return o
    return dict(o)


def get_positions(client: SchwabClient) -> dict[str, dict]:
    """{symbol: {"qty": longQty, "avg": averagePrice}} for held longs."""
    out: dict[str, dict] = {}
    try:
        for acct in client.get_accounts(include_positions=True):
            d = _as_dict(getattr(acct, "securities_account", None))
            for p in (d.get("positions") or []):
                pd = _as_dict(p)
                instr = pd.get("instrument") or {}
                sym = instr.get("symbol") if isinstance(instr, dict) else None
                qty = pd.get("longQuantity") or 0
                if sym and qty > 0:
                    out[sym] = {"qty": qty, "avg": pd.get("averagePrice") or 0}
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not read positions: {exc}")
    return out


def get_working_symbols(client: SchwabClient, account_number: str) -> set[str]:
    """Symbols with an open/working/pending order — so we never double-order."""
    working: set[str] = set()
    open_states = {"WORKING", "PENDING_ACTIVATION", "QUEUED", "ACCEPTED",
                   "AWAITING_PARENT_ORDER", "AWAITING_CONDITION", "NEW"}
    try:
        now = datetime.now(timezone.utc)
        orders = client.get_orders(
            account_number,
            from_entered_time=now - timedelta(days=2),
            to_entered_time=now + timedelta(minutes=5),
        )
        for o in orders:
            od = _as_dict(o)
            status = str(od.get("status", "")).upper()
            if status and status not in open_states:
                continue
            for leg in (od.get("orderLegCollection") or []):
                ld = _as_dict(leg)
                instr = ld.get("instrument") or {}
                sym = instr.get("symbol") if isinstance(instr, dict) else None
                if sym:
                    working.add(sym)
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not read working orders: {exc}")
    return working


def last_price(client: SchwabClient, symbol: str) -> float | None:
    try:
        q = client.get_quotes(symbol)
        d = _as_dict(q)
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


def validate_entry(order: dict) -> tuple[bool, str]:
    if order.get("action") != "BUY":
        return False, "not a BUY"
    if order.get("instrument", "stock") != "stock":
        return False, "only stocks supported for now"
    qty = order.get("quantity") or 0
    limit = order.get("limit_price") or 0
    tp = order.get("take_profit") or 0
    sl = order.get("stop_loss") or 0
    if qty <= 0 or limit <= 0:
        return False, "bad quantity/limit_price"
    if qty * limit > MAX_DOLLARS_PER_TRADE:
        return False, f"${qty*limit:.2f} exceeds ${MAX_DOLLARS_PER_TRADE:.0f} cap"
    if tp <= 0 or sl <= 0:
        return False, "brain must supply take_profit and stop_loss prices"
    if tp < limit * (1 + MIN_TP_OVER_ENTRY):
        return False, f"take_profit ${tp:.2f} not above entry ${limit:.2f}"
    if sl > limit * (1 - MIN_STOP_UNDER_ENTRY):
        return False, f"stop_loss ${sl:.2f} not below entry ${limit:.2f}"
    return True, "ok"


def open_bracket(client, acct, order: dict):
    sym = order["symbol"]
    qty = int(order["quantity"])
    limit = round(float(order["limit_price"]), 2)
    tp = round(float(order["take_profit"]), 2)
    sl = round(float(order["stop_loss"]), 2)
    if DRY_RUN:
        print(f"[{sym}] DRY-RUN: would BUY {qty} @ ${limit:.2f} "
              f"| target ${tp:.2f} | stop ${sl:.2f} | ${qty*limit:.2f} (GTC bracket)")
        return
    try:
        bracket = client.create_bracket_order(
            symbol=sym, quantity=qty, instruction=Instruction.buy,
            entry_price=limit, profit_target_price=tp, stop_loss_price=sl,
            order_type=OrderType.limit, duration=Duration.good_till_cancel,
        )
        client.place_order(acct.hash_value, bracket)
        print(f"[{sym}] ✅ LIVE BUY {qty} @ ${limit:.2f} | target ${tp:.2f} | stop ${sl:.2f}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{sym}] entry error: {exc}")


def sell_to_close(client, acct, symbol: str, qty, why: str):
    qty = int(qty)
    if qty <= 0:
        return
    price = last_price(client, symbol)
    if DRY_RUN:
        px = f"${price:.2f}" if price else "market"
        print(f"[{symbol}] DRY-RUN: would SELL {qty} @ {px} to close ({why})")
        return
    try:
        if price:
            order = client.create_limit_order(
                symbol=symbol, quantity=qty, limit_price=round(price, 2),
                instruction=Instruction.sell, duration=Duration.day,
            )
        else:
            order = client.create_market_order(
                symbol=symbol, quantity=qty, instruction=Instruction.sell,
                duration=Duration.day,
            )
        client.place_order(acct.hash_value, order)
        print(f"[{symbol}] ✅ LIVE SELL {qty} to close ({why})")
    except Exception as exc:  # noqa: BLE001
        print(f"[{symbol}] sell error: {exc}")


def main() -> int:
    mode = "DRY-RUN (no real orders)" if DRY_RUN else "LIVE (real orders!)"
    print(f"=== Executor | mode: {mode} ===")

    client = get_client()
    acct = client.get_account_numbers().accounts[0]
    positions = get_positions(client)
    working = get_working_symbols(client, acct.account_number)
    print(f"Held: {', '.join(positions) or '(none)'} | Working orders: {', '.join(working) or '(none)'}")

    generated_utc, orders = load_orders()
    fresh = bool(orders) and is_fresh(generated_utc)

    # 1. Brain SELL signals — close held positions the brain wants out of.
    if fresh:
        for o in orders:
            if o.get("action") == "SELL":
                sym = o.get("symbol")
                if sym in positions:
                    sell_to_close(client, acct, sym, positions[sym]["qty"], "brain SELL signal")
                else:
                    print(f"[{sym}] SELL signal ignored — not held")

    # 2. New bracket entries from fresh BUY picks.
    if not fresh:
        print("No fresh BUY picks to act on.")
        print("=== done ===")
        return 0

    for order in orders:
        if order.get("action") != "BUY":
            continue
        sym = order.get("symbol", "?")
        ok, why = validate_entry(order)
        if not ok:
            print(f"[{sym}] SKIP entry — {why}")
            continue
        if sym in positions:
            print(f"[{sym}] SKIP entry — already holding")
            continue
        if sym in working:
            print(f"[{sym}] SKIP entry — already has a working/pending order")
            continue
        open_bracket(client, acct, order)

    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
