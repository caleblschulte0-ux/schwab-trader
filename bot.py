"""Day-trade executor — simple marketable-limit entries + software-managed exits.

Why this design (learned the hard way on a small cash account):
  * BRACKET/OCO orders were repeatedly auto-canceled by Schwab on this account.
  * Buy limits priced off the brain's (stale, web-sourced) number sat BELOW the
    live ask and never filled.
So entries are now DEAD SIMPLE and priced off Schwab's LIVE quote:
  ENTRY  = plain BUY limit at (live ask * 1.002) -> marketable, fills now at the
           real price. DAY duration. No bracket.
  EXITS  = managed in software here (runs on a schedule): for each held position,
           if price >= the pick's take_profit or <= its stop_loss, SELL to close.
           Also honors a brain {"action":"SELL"} signal.

Ground truth: every run the bot writes the account's REAL positions to
signals/holdings.json. The brain reads that file to know what it actually owns —
no hardcoding holdings anywhere.

Risk rules still enforced in code (your one rule is safe):
  * BUY-only; we only ever SELL shares we already own (never short).
  * quantity * entry <= MAX_DOLLARS_PER_TRADE.
  * skip symbols already HELD, with an OPEN buy, OR bought in the last
    RECENT_BUY_COOLDOWN_MIN minutes (closes the settlement-lag double-buy gap);
    if orders can't be read, place NOTHING (fail safe).
  * don't chase: skip a BUY if the live ask is already > limit_price * (1+MAX_SLIPPAGE).

DRY_RUN defaults to "true". Set a DRY_RUN repo variable to "false" to go live.

Secrets (GitHub Actions): SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_REFRESH_TOKEN
Optional: SCHWAB_CALLBACK_URL, DRY_RUN
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from schwab import SchwabAuth, SchwabClient
from schwab.models.generated.trading_models import Instruction, Duration

# ===== GUARDRAILS / KNOBS =====
MAX_DOLLARS_PER_TRADE = 65.00   # never spend more than this on one entry
MAX_SIGNAL_AGE_HOURS  = 18      # ignore a stale orders.json
MAX_SLIPPAGE          = 0.03    # skip a BUY if live ask is >3% above the pick's limit
MARKETABLE_BUFFER     = 0.002   # buy limit = live ask * (1 + this) so it fills now
ORDERS_FILE           = "signals/orders.json"
HOLDINGS_FILE         = "signals/holdings.json"
MIN_TP_OVER_ENTRY     = 0.005
MIN_STOP_UNDER_ENTRY  = 0.005
RECENT_BUY_COOLDOWN_MIN = 60    # don't re-buy a symbol bought in the last hour
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


def _as_dict(o):
    if o is None:
        return {}
    if hasattr(o, "model_dump"):
        return o.model_dump()
    if isinstance(o, dict):
        return o
    return dict(o)


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


def get_positions(client: SchwabClient) -> dict[str, dict]:
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


def write_holdings(positions: dict) -> None:
    """Write the account's REAL holdings to a file the brain trusts as ground truth."""
    data = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "holdings": [
            {"symbol": s, "quantity": p["qty"], "avg_price": p["avg"]}
            for s, p in sorted(positions.items())
        ],
    }
    try:
        os.makedirs(os.path.dirname(HOLDINGS_FILE), exist_ok=True)
        with open(HOLDINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        print(f"Wrote {HOLDINGS_FILE}: {len(data['holdings'])} holding(s)")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not write holdings file: {exc}")


def _parse_dt(val):
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except ValueError:
        return None


def get_blocked_buy_symbols(client: SchwabClient, account_hash: str) -> tuple[set[str], bool]:
    """Symbols we must NOT (re)buy this run: those with an OPEN buy order, OR a
    BUY order that was entered/filled within the last RECENT_BUY_COOLDOWN_MIN
    minutes. The cooldown closes the settlement-lag gap where a just-filled buy
    isn't in positions yet, which previously caused double-buys.
    Returns (symbols, ok); ok=False means we couldn't read orders (fail safe)."""
    blocked: set[str] = set()
    open_states = {"WORKING", "PENDING_ACTIVATION", "QUEUED", "ACCEPTED",
                   "AWAITING_PARENT_ORDER", "AWAITING_CONDITION", "NEW",
                   "PENDING_RECALL", "AWAITING_MANUAL_REVIEW", "AWAITING_STOP_CONDITION"}
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=RECENT_BUY_COOLDOWN_MIN)
        orders = client.get_orders(
            account_hash,
            from_entered_time=now - timedelta(days=5),
            to_entered_time=now + timedelta(minutes=5),
        )
        for o in orders:
            od = _as_dict(o)
            status = str(od.get("status", "")).upper()
            if status == "CANCELED" or status == "REJECTED" or status == "EXPIRED":
                continue
            entered = _parse_dt(od.get("enteredTime"))
            recent = entered is not None and entered >= cutoff
            for leg in (od.get("orderLegCollection") or []):
                ld = _as_dict(leg)
                instr = ld.get("instrument") or {}
                sym = instr.get("symbol") if isinstance(instr, dict) else None
                if not sym:
                    continue
                instruction = str(ld.get("instruction", "")).upper()
                # Block if a BUY is currently open, or any recent (open/filled) buy.
                if instruction.startswith("BUY") and (status in open_states or recent):
                    blocked.add(sym)
        return blocked, True
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not read orders: {exc}")
        return blocked, False


def quote(client: SchwabClient, symbol: str) -> dict:
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
        return found
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) no quote for {symbol}: {exc}")
        return {}


def live_ask(q: dict) -> float | None:
    for k in ("askprice", "ask_price", "ask", "lastprice", "last_price", "mark"):
        if k in q and q[k]:
            return q[k]
    return None


def live_last(q: dict) -> float | None:
    for k in ("lastprice", "last_price", "mark", "bidprice", "bid_price"):
        if k in q and q[k]:
            return q[k]
    return None


def validate_pick(order: dict) -> tuple[bool, str]:
    if order.get("action") != "BUY":
        return False, "not a BUY"
    if order.get("instrument", "stock") != "stock":
        return False, "only stocks supported"
    qty = order.get("quantity") or 0
    limit = order.get("limit_price") or 0
    tp = order.get("take_profit") or 0
    sl = order.get("stop_loss") or 0
    if qty <= 0 or limit <= 0:
        return False, "bad quantity/limit_price"
    if tp <= 0 or sl <= 0:
        return False, "missing take_profit/stop_loss"
    if tp < limit * (1 + MIN_TP_OVER_ENTRY) or sl > limit * (1 - MIN_STOP_UNDER_ENTRY):
        return False, "tp/stop not on correct sides of entry"
    return True, "ok"


def buy(client, acct, sym: str, qty: int, limit: float):
    if DRY_RUN:
        print(f"[{sym}] DRY-RUN: would BUY {qty} @ ${limit:.2f} = ${qty*limit:.2f}")
        return
    try:
        order = client.create_limit_order(
            symbol=sym, quantity=qty, limit_price=round(limit, 2),
            instruction=Instruction.buy, duration=Duration.day,
        )
        client.place_order(acct.hash_value, order)
        print(f"[{sym}] ✅ LIVE BUY {qty} @ ${limit:.2f} (marketable limit)")
    except Exception as exc:  # noqa: BLE001
        print(f"[{sym}] buy error: {exc}")


def sell(client, acct, sym: str, qty: int, limit: float, why: str):
    if DRY_RUN:
        print(f"[{sym}] DRY-RUN: would SELL {qty} @ ${limit:.2f} to close ({why})")
        return
    try:
        order = client.create_limit_order(
            symbol=sym, quantity=qty, limit_price=round(limit, 2),
            instruction=Instruction.sell, duration=Duration.day,
        )
        client.place_order(acct.hash_value, order)
        print(f"[{sym}] ✅ LIVE SELL {qty} @ ${limit:.2f} to close ({why})")
    except Exception as exc:  # noqa: BLE001
        print(f"[{sym}] sell error: {exc}")


def main() -> int:
    mode = "DRY-RUN (no real orders)" if DRY_RUN else "LIVE (real orders!)"
    print(f"=== Executor | mode: {mode} ===")

    client = get_client()
    acct = client.get_account_numbers().accounts[0]
    positions = get_positions(client)
    write_holdings(positions)  # ground-truth holdings file for the brain
    blocked, orders_ok = get_blocked_buy_symbols(client, acct.hash_value)
    print(f"Held: {', '.join(positions) or '(none)'} | No-rebuy: "
          f"{', '.join(blocked) or '(none)'} | read_ok={orders_ok}")

    generated_utc, orders = load_orders()
    fresh = bool(orders) and is_fresh(generated_utc)
    # Map each symbol -> its tp/stop from the latest picks (for exit management).
    levels = {o["symbol"]: o for o in orders if o.get("action") == "BUY"} if orders else {}
    brain_sells = {o.get("symbol") for o in orders if o.get("action") == "SELL"} if fresh else set()

    # ---- EXITS: manage held positions (sell-to-close on target/stop/brain) ----
    for sym, pos in positions.items():
        q = quote(client, sym)
        last = live_last(q)
        pick = levels.get(sym, {})
        tp = pick.get("take_profit")
        sl = pick.get("stop_loss")
        if sym in brain_sells:
            sell(client, acct, sym, int(pos["qty"]), last or pos["avg"], "brain SELL")
        elif last and tp and last >= tp:
            sell(client, acct, sym, int(pos["qty"]), last, f"hit target ${tp}")
        elif last and sl and last <= sl:
            sell(client, acct, sym, int(pos["qty"]), last, f"hit stop ${sl}")
        else:
            tptxt = f"${tp}" if tp else "?"
            sltxt = f"${sl}" if sl else "?"
            print(f"[{sym}] hold — last ${last} (target {tptxt} / stop {sltxt})")

    # ---- ENTRIES: only fresh BUY picks, priced off the LIVE ask ----
    if not fresh:
        print("No fresh BUY picks.")
        print("=== done ===")
        return 0
    if not orders_ok:
        print("SKIP entries — could not read existing orders (fail-safe).")
        print("=== done ===")
        return 0

    for order in orders:
        if order.get("action") != "BUY":
            continue
        sym = order.get("symbol", "?")
        ok, why = validate_pick(order)
        if not ok:
            print(f"[{sym}] SKIP — {why}")
            continue
        if sym in positions:
            print(f"[{sym}] SKIP — already holding")
            continue
        if sym in blocked:
            print(f"[{sym}] SKIP — open or recent buy order (no double-buy)")
            continue

        q = quote(client, sym)
        ask = live_ask(q)
        if not ask:
            print(f"[{sym}] SKIP — no live quote")
            continue
        pick_limit = float(order["limit_price"])
        if ask > pick_limit * (1 + MAX_SLIPPAGE):
            print(f"[{sym}] SKIP — ran away: live ask ${ask:.2f} > limit ${pick_limit:.2f} +{MAX_SLIPPAGE*100:.0f}%")
            continue

        # Marketable limit at the live ask so it actually fills now.
        entry = round(ask * (1 + MARKETABLE_BUFFER), 2)
        qty = int(order["quantity"])
        # Re-check the dollar cap against the REAL entry price, and trim qty if needed.
        while qty > 0 and qty * entry > MAX_DOLLARS_PER_TRADE:
            qty -= 1
        if qty <= 0:
            print(f"[{sym}] SKIP — 1 share at ${entry:.2f} exceeds ${MAX_DOLLARS_PER_TRADE:.0f} cap")
            continue
        buy(client, acct, sym, qty, entry)

    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
