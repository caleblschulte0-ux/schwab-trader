"""Step 2: Pull account balances and positions.

Run it with:  python accounts.py

This loads your saved tokens, asks Schwab for every account linked to your
login, and prints balances plus current positions for each.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from schwab_session import get_client


def _as_dict(obj: Any) -> Dict[str, Any]:
    """Schwab returns balances/positions as raw JSON dicts (camelCase keys).

    A few library models wrap them, so normalize anything to a plain dict.
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(by_alias=True)
    if hasattr(obj, "root"):
        return _as_dict(obj.root)
    return dict(obj)


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def print_account(account: Any) -> None:
    sec = _as_dict(getattr(account, "securities_account", account))
    # Some responses nest under "securitiesAccount"; unwrap if needed.
    if "securitiesAccount" in sec:
        sec = _as_dict(sec["securitiesAccount"])

    acct_no = sec.get("accountNumber", "<unknown>")
    acct_type = sec.get("type", "")
    print("\n" + "=" * 64)
    print(f"Account {acct_no}  ({acct_type})")
    print("=" * 64)

    balances = _as_dict(sec.get("currentBalances"))
    if balances:
        print("Balances:")
        # Different account types expose different keys; show the common ones
        # that exist, plus everything else for completeness.
        preferred = [
            ("Total account value", "liquidationValue"),
            ("Cash balance", "cashBalance"),
            ("Available funds", "availableFunds"),
            ("Buying power", "buyingPower"),
            ("Equity", "equity"),
        ]
        shown = set()
        for label, key in preferred:
            if key in balances:
                print(f"  {label:<22} {_money(balances[key])}")
                shown.add(key)
        for key, value in balances.items():
            if key not in shown:
                print(f"  {key:<22} {_money(value)}")
    else:
        print("Balances: (none returned)")

    positions: List[Dict[str, Any]] = [
        _as_dict(p) for p in (sec.get("positions") or [])
    ]
    print(f"\nPositions ({len(positions)}):")
    if not positions:
        print("  (no open positions)")
        return

    header = f"  {'SYMBOL':<10}{'QTY':>10}{'AVG PRICE':>14}{'MKT VALUE':>16}{'DAY P/L':>14}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for pos in positions:
        instrument = _as_dict(pos.get("instrument"))
        symbol = instrument.get("symbol", "?")
        long_qty = pos.get("longQuantity") or 0
        short_qty = pos.get("shortQuantity") or 0
        qty = long_qty - short_qty
        avg_price = pos.get("averagePrice", 0)
        mkt_value = pos.get("marketValue", 0)
        day_pl = pos.get("currentDayProfitLoss", 0)
        print(
            f"  {symbol:<10}{qty:>10.4g}"
            f"{_money(avg_price):>14}{_money(mkt_value):>16}{_money(day_pl):>14}"
        )


def main() -> int:
    client = get_client()
    accounts = client.get_accounts(include_positions=True)
    if not accounts:
        print("No accounts found for this login.")
        return 0
    print(f"Found {len(accounts)} account(s).")
    for account in accounts:
        print_account(account)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        raise SystemExit(1)
