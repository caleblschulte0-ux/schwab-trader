"""Step 1: One-time OAuth login.

Schwab uses the OAuth 2.0 "authorization code" flow. You can't just send your
App Key and Secret — you have to prove (once) that a real human with Schwab
login credentials authorized this app. The flow:

  1. We print an authorization URL.
  2. You open it in a browser and log in to Schwab + approve the app.
  3. Schwab redirects your browser to your callback URL (https://127.0.0.1)
     with a one-time `code` in the address bar. The page itself won't load
     (nothing is listening on 127.0.0.1) -- that's expected. You only need the
     URL from the address bar.
  4. You paste that full redirected URL back here.
  5. We exchange the code for an access token + refresh token and save them to
     token.json. From then on the other scripts reuse those tokens.

Run it with:  python auth_setup.py
"""
from __future__ import annotations

import sys
from urllib.parse import parse_qs, unquote, urlparse

from config import load_settings
from schwab_session import build_auth, save_tokens


def extract_code(pasted: str) -> str:
    """Pull the authorization code out of whatever the user pasted.

    Accepts either the full redirected URL (https://127.0.0.1/?code=...&...)
    or a bare code. Schwab codes are URL-encoded and end in '@', so we decode.
    """
    pasted = pasted.strip()
    if "code=" in pasted:
        query = urlparse(pasted).query
        codes = parse_qs(query).get("code")
        if not codes:
            raise ValueError("Could not find a 'code' parameter in that URL.")
        return codes[0]
    # Assume the user pasted just the code; make sure it's decoded.
    return unquote(pasted)


def main() -> int:
    settings = load_settings()
    auth = build_auth(settings)

    auth_url = auth.get_authorization_url()
    print("=" * 70)
    print("STEP 1 of 1: Authorize this app with Schwab")
    print("=" * 70)
    print("\n1) Open this URL in your browser and log in to Schwab:\n")
    print(f"   {auth_url}\n")
    print("2) Approve the app. Your browser will redirect to a URL that starts")
    print(f"   with {settings.callback_url} and contains '?code=...'.")
    print("   The page will look like it failed to load -- that is normal.")
    print("3) Copy the ENTIRE URL from your browser's address bar.\n")

    pasted = input("Paste the full redirected URL here:\n> ").strip()
    if not pasted:
        print("No URL provided. Aborting.", file=sys.stderr)
        return 1

    try:
        code = extract_code(pasted)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("\nExchanging the authorization code for tokens...")
    try:
        auth.exchange_code_for_tokens(code)
    except Exception as exc:  # noqa: BLE001
        print(f"Token exchange failed: {exc}", file=sys.stderr)
        print(
            "\nCommon causes:\n"
            "  * The code expired (it's only valid for ~30 seconds) -- re-run "
            "and paste quickly.\n"
            "  * The callback URL in .env doesn't EXACTLY match the one "
            "registered for your app.\n"
            "  * App Key / Secret are wrong.",
            file=sys.stderr,
        )
        return 1

    # build_auth() already patched the auth object to save on every token
    # update, so token.json is written. Save again explicitly to be safe.
    save_tokens(auth, settings)

    print("\n" + "=" * 70)
    print(f"Success! Tokens saved to {settings.token_path}")
    print("=" * 70)
    print("\nNext steps:")
    print("  * python accounts.py        # view balances & positions")
    print("  * python place_order.py ... # place a limit order")
    print("\nNote: the refresh token lasts ~7 days. After that, re-run this "
          "script to log in again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
