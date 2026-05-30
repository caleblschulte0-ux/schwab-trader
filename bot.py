"""Executor — turns the AI brain's picks into orders (dry-run by default).

The brain (a scheduled Claude routine) researches the market and writes its
picks to `signals/orders.json`. This bot runs on a schedule via GitHub Actions,
reads that file, RE-CHECKS every guardrail in code (so a bad pick can't slip
through), skips anything already held, and places — or in DRY_RUN, just logs —
a bracket order (entry + auto take-profit + auto stop-loss) for each pick.

SAFETY:
  * DRY_RUN defaults to "true": nothing real trades until a DRY_RUN repo
    variable is set to "false".
  * Buy-only, hard dollar cap per trade, freshness check, and held-symbol skip
    are all enforced here regardless of what the brain wrote.

  ⚠️ BEFORE GOING LIVE: add open-order de-dup. Today it skips symbols you already
  hold a position in, but two runs inside the freshness window could still place
  duplicate *orders* for a brand-new pick. Harmless in DRY_RUN (just re-logs);
  must be hardened before DRY_RUN is turned off.

Secrets (GitHub Actions): SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_REFRESH_TOKEN
Optional: SCHWAB_CALLBACK_URL, DRY_RUN
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from schwab import SchwabAuth, SchwabClient
from schwab.models.generated.trading_models import Instruction, Duration, OrderType

# ===== GUARDRAILS (enforced here no matter what the brain says) =====
MAX_DOLLARS_PER_TRADE = 65.00   # never spend more than this on one order
TAKE_PROFIT_PCT       = 0.08    # bracket auto-sell target (+8%)
STOP_LOSS_PCT         = 0.05    # bracket auto-sell stop (-5%)
MAX_SIGNAL_AGE_HOURS  = 18      # ignore a stale orders.json (don't trade old picks)
ORDERS_FILE           = "signals/orders.json"
# ====================================================================

APP_KEY       = os.environ["SCHWAB_APP_KEY"].strip()
APP_SECRET    = os.environ["SCHWAB_APP_SECRET"].strip()
REFRESH_TOKEN = os.environ["SCHWAB_REFRESH_TOKEN"].strip()
CALLBACK      = os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1/").strip()
DRY_RUN       = os.environ.get("DRY_RUN", "true").strip().lower() != "false"


def get_client() -> SchwabClient:
    """Authenticate using the stored refresh token (no browser needed)."""
    auth = SchwabAuth(APP_KEY, APP_SECRET, CALLBACK)
    auth.refresh_token = REFRESH_TOKEN
    try:
        auth.refresh_access_token()
    except Exception as exc:  # noqa: BLE001 - surface Schwab's exact reason
        resp = getattr(exc, "response", None)
        if resp is not None:
            print(f"Schwab token endpoint said: HTTP {resp.status_code} -> {resp.text}")
        raise
    return SchwabClient(APP_KEY, APP_SECRET, CALLBACK, auth=auth)


def load_orders() -> tuple[str | None, list[dict]]:
    if not os.path.exists(ORDERS_FILE):
        print(f"No {ORDERS_FILE} on this branch — the brain hasn't written picks here.")
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


def passes_guardrails(order: dict) -> tuple[bool, str]:
    if order.get("action") != "BUY":
        return False, "not a BUY (buy-only)"
    if order.get("instrument", "stock") != "stock":
        return False, "only stocks supported for now (puts come later)"
    qty = order.get("quantity") or 0
    limit = order.get("limit_price") or 0
    if qty <= 0 or limit <= 0:
        return False, "bad quantity/limit_price"
    cost = qty * limit
    if cost > MAX_DOLLARS_PER_TRADE:
        return False, f"${cost:.2f} exceeds ${MAX_DOLLARS_PER_TRADE:.0f} cap"
    return True, "ok"


def held_symbols(client: SchwabClient) -> set[str]:
    """Symbols already held, so we don't double-buy the same name."""
    held: set[str] = set()
    try:
        for acct in client.get_accounts(include_positions=True):
            sec = getattr(acct, "securities_account", None)
            d = sec.model_dump() if hasattr(sec, "model_dump") else (sec or {})
            for p in (d.get("positions") or []):
                pd = p.model_dump() if hasattr(p, "model_dump") else (p or {})
                instr = pd.get("instrument") or {}
                sym = instr.get("symbol") if isinstance(instr, dict) else None
                if sym:
                    held.add(sym)
    except Exception as exc:  # noqa: BLE001 - never let this break the run
        print(f"(warn) could not read positions: {exc}")
    return held


def main() -> int:
    mode = "DRY-RUN (no real orders)" if DRY_RUN else "LIVE (real orders!)"
    print(f"=== Executor starting | mode: {mode} ===")

    generated_utc, orders = load_orders()
    if not orders:
        print("No picks to act on. Done.")
        return 0
    if not is_fresh(generated_utc):
        print("Signal file is stale — skipping so we don't trade old picks.")
        return 0

    client = get_client()
    acct = client.get_account_numbers().accounts[0]
    held = held_symbols(client)

    for order in orders:
        sym = order.get("symbol", "?")
        ok, why = passes_guardrails(order)
        if not ok:
            print(f"[{sym}] SKIP — {why}")
            continue
        if sym in held:
            print(f"[{sym}] SKIP — already holding a position")
            continue

        qty = int(order["quantity"])
        limit = round(float(order["limit_price"]), 2)
        tp = round(limit * (1 + TAKE_PROFIT_PCT), 2)
        sl = round(limit * (1 - STOP_LOSS_PCT), 2)

        if DRY_RUN:
            print(f"[{sym}] DRY-RUN: would BUY {qty} @ ${limit:.2f} "
                  f"(TP ${tp:.2f} / SL ${sl:.2f}) = ${qty * limit:.2f}")
            continue
        try:
            bracket = client.create_bracket_order(
                symbol=sym, quantity=qty, instruction=Instruction.buy,
                entry_price=limit, profit_target_price=tp, stop_loss_price=sl,
                order_type=OrderType.limit, duration=Duration.good_till_cancel,
            )
            client.place_order(acct.hash_value, bracket)
            print(f"[{sym}] ✅ LIVE BUY {qty} @ ${limit:.2f} | TP ${tp:.2f} | SL ${sl:.2f}")
        except Exception as exc:  # noqa: BLE001 - keep going on per-order errors
            print(f"[{sym}] order error: {exc}")

    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
