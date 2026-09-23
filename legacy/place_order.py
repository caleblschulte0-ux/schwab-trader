"""Step 3: Place a basic limit order.

A LIMIT order only fills at your price or better:
  * BUY limit  -> fills at or BELOW your limit price.
  * SELL limit -> fills at or ABOVE your limit price.

IMPORTANT: an account number you see in the Schwab app is NOT what the API
uses. The API uses an encrypted "hash" value, which we fetch automatically.

Usage:
  python place_order.py BUY AAPL 1 185.00
  python place_order.py SELL AAPL 1 999.00 --account <ACCOUNT_NUMBER>
  python place_order.py BUY AAPL 1 185.00 --yes      # skip confirmation

By default this asks you to confirm before sending. Start with a tiny quantity
and a limit price far from the market (so it WON'T fill) while you test.
"""
from __future__ import annotations

import argparse
import sys

from schwab.models.generated.trading_models import Instruction

from schwab_session import get_client


def resolve_account_hash(client, account_number: str | None) -> tuple[str, str]:
    """Return (display_account_number, encrypted_hash) for the order.

    If account_number is given, match it; otherwise use the first account.
    """
    account_numbers = client.get_account_numbers()
    accounts = account_numbers.accounts
    if not accounts:
        raise RuntimeError("No accounts are linked to this login.")

    if account_number:
        for acct in accounts:
            if acct.account_number == account_number:
                return acct.account_number, acct.hash_value
        available = ", ".join(a.account_number for a in accounts)
        raise RuntimeError(
            f"Account {account_number!r} not found. Available: {available}"
        )

    if len(accounts) > 1:
        available = ", ".join(a.account_number for a in accounts)
        print(
            f"Note: multiple accounts found ({available}). Using the first one. "
            "Pass --account to choose a specific one.",
            file=sys.stderr,
        )
    return accounts[0].account_number, accounts[0].hash_value


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Place a basic limit order.")
    parser.add_argument("side", choices=["BUY", "SELL"], type=str.upper,
                        help="BUY or SELL")
    parser.add_argument("symbol", type=str.upper, help="Ticker symbol, e.g. AAPL")
    parser.add_argument("quantity", type=int, help="Number of shares")
    parser.add_argument("limit_price", type=float, help="Limit price per share")
    parser.add_argument("--account", default=None,
                        help="Account number (defaults to first account)")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.quantity <= 0:
        print("Quantity must be a positive whole number.", file=sys.stderr)
        return 1
    if args.limit_price <= 0:
        print("Limit price must be greater than 0.", file=sys.stderr)
        return 1

    client = get_client()
    display_acct, account_hash = resolve_account_hash(client, args.account)

    instruction = Instruction.buy if args.side == "BUY" else Instruction.sell

    estimated = args.quantity * args.limit_price
    print("\nAbout to place this order:")
    print(f"  Account:     {display_acct}")
    print(f"  Action:      {args.side} {args.quantity} {args.symbol}")
    print(f"  Order type:  LIMIT @ ${args.limit_price:,.2f}")
    print("  Time-in-force: DAY")
    print(f"  Est. {'cost' if args.side == 'BUY' else 'proceeds'}: ${estimated:,.2f}")

    if not args.yes:
        confirm = input("\nType 'yes' to send this order: ").strip().lower()
        if confirm != "yes":
            print("Cancelled. No order was placed.")
            return 0

    # Build the limit order object, then place it.
    order = client.create_limit_order(
        symbol=args.symbol,
        quantity=args.quantity,
        limit_price=args.limit_price,
        instruction=instruction,
    )
    client.place_order(account_hash, order)

    print("\nOrder submitted to Schwab.")
    print("Check status in the Schwab app, or build on top of "
          "client.get_orders(...) to track it programmatically.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except RuntimeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        raise SystemExit(1)
