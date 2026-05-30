"""Scheduled Schwab trading bot — designed to run on GitHub Actions (free).

It authenticates using credentials stored as GitHub repository *secrets*
(never committed), checks a simple rule for each symbol on a watchlist, and
either logs the intended trade (DRY_RUN) or places a limit order.

SAFETY: DRY_RUN defaults to "true". It will NOT place real orders until you
set the DRY_RUN secret/variable to "false" yourself. Watch the logs first.

Required environment (set as GitHub Actions secrets):
  SCHWAB_APP_KEY
  SCHWAB_APP_SECRET
  SCHWAB_REFRESH_TOKEN   (from token.json after you log in via Colab)
Optional:
  SCHWAB_CALLBACK_URL    (defaults to https://127.0.0.1/)
  DRY_RUN                ("true" = log only [default], "false" = place real orders)
"""
from __future__ import annotations

import os
import sys

from schwab import SchwabAuth, SchwabClient
from schwab.models.generated.trading_models import Instruction, Duration, OrderType

# ============== STRATEGY + GUARDRAILS (edit these) ==============
WATCHLIST       = ["AAPL", "MSFT"]  # symbols the bot is allowed to consider
MAX_SHARES      = 1                 # never buy more than this many shares
MAX_DOLLARS     = 50.00             # never spend more than this on one order
BUY_DIP_PCT     = 0.02              # buy if price is >= 2% below today's open
TAKE_PROFIT_PCT = 0.05             # auto-sell for +5% profit
STOP_LOSS_PCT   = 0.03             # auto-sell to cap a -3% loss
# ===============================================================

APP_KEY       = os.environ["SCHWAB_APP_KEY"]
APP_SECRET    = os.environ["SCHWAB_APP_SECRET"]
REFRESH_TOKEN = os.environ["SCHWAB_REFRESH_TOKEN"]
CALLBACK      = os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1/")
DRY_RUN       = os.environ.get("DRY_RUN", "true").strip().lower() != "false"


def get_client() -> SchwabClient:
    """Authenticate using the stored refresh token (no browser needed)."""
    auth = SchwabAuth(APP_KEY, APP_SECRET, CALLBACK)
    auth.refresh_token = REFRESH_TOKEN
    auth.refresh_access_token()  # mint a fresh ~30-min access token
    return SchwabClient(APP_KEY, APP_SECRET, CALLBACK, auth=auth)


def quote_prices(client: SchwabClient, symbol: str) -> dict:
    """Best-effort extraction of price fields from a Schwab quote."""
    q = client.get_quotes(symbol)
    data = q.model_dump() if hasattr(q, "model_dump") else dict(q)
    prices: dict[str, float] = {}

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (int, float)):
                    prices.setdefault(k.lower(), float(v))
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return prices


def pick(prices: dict, *names: str):
    for n in names:
        if n in prices:
            return prices[n]
    return None


def decide(symbol: str, prices: dict):
    """Return (action, quantity, limit_price, reason) — a tiny example rule."""
    last = pick(prices, "lastprice", "last_price", "mark")
    open_ = pick(prices, "openprice", "open_price")
    if last is None or open_ is None or open_ == 0:
        return "HOLD", 0, 0.0, "missing price data"

    change = (last - open_) / open_
    if change <= -BUY_DIP_PCT:
        # Buy at the current price, capped by guardrails.
        qty = max(1, min(MAX_SHARES, int(MAX_DOLLARS // last)))
        if qty * last > MAX_DOLLARS:
            return "HOLD", 0, 0.0, f"1 share (${last:.2f}) exceeds ${MAX_DOLLARS} cap"
        return "BUY", qty, round(last, 2), f"down {change*100:.1f}% from open"
    return "HOLD", 0, 0.0, f"only {change*100:.1f}% from open (need <= -{BUY_DIP_PCT*100:.0f}%)"


def main() -> int:
    mode = "DRY-RUN (no real orders)" if DRY_RUN else "LIVE (real orders!)"
    print(f"=== Schwab bot starting | mode: {mode} ===")
    client = get_client()
    acct = client.get_account_numbers().accounts[0]

    for symbol in WATCHLIST:
        try:
            prices = quote_prices(client, symbol)
            action, qty, limit, reason = decide(symbol, prices)
            print(f"[{symbol}] {action} {qty} @ {limit}  ({reason})")
            if action != "BUY":
                continue
            tp = round(limit * (1 + TAKE_PROFIT_PCT), 2)
            sl = round(limit * (1 - STOP_LOSS_PCT), 2)
            if DRY_RUN:
                print(f"   DRY-RUN: would BUY {qty} {symbol} @ ${limit:.2f} "
                      f"(take-profit ${tp:.2f} / stop ${sl:.2f})")
                continue
            # Bracket = entry + auto take-profit + auto stop-loss, resting GTC,
            # so each position manages its own exit with no further watching.
            order = client.create_bracket_order(
                symbol=symbol, quantity=qty, instruction=Instruction.buy,
                entry_price=limit, profit_target_price=tp, stop_loss_price=sl,
                order_type=OrderType.limit, duration=Duration.good_till_cancel,
            )
            client.place_order(acct.hash_value, order)
            print(f"   ✅ LIVE: BUY {qty} {symbol} @ ${limit:.2f} "
                  f"| TP ${tp:.2f} | SL ${sl:.2f}")
        except Exception as exc:  # noqa: BLE001 - keep going on per-symbol errors
            print(f"[{symbol}] error: {exc}")

    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
