# schwab-trader

A small, beginner-friendly Python integration for the **Charles Schwab Trader
API**, built on the [`schwab-trader`](https://pypi.org/project/schwab-trader/)
library. It covers the three things you asked for:

1. **Auth setup** — log in once via OAuth, cache the tokens.
2. **Account balances & positions** — see what you hold.
3. **Place a basic limit order** — buy/sell at a price you choose.

> ⚠️ **This places *real* orders against a *real* brokerage account.** Test
> with tiny quantities and limit prices far from the market so nothing fills
> until you trust it.

---

## How the pieces fit together

| File | What it does |
|------|--------------|
| `.env` | Your secrets (App Key, Secret, callback URL). **Gitignored.** |
| `.env.example` | A template to copy into `.env`. |
| `config.py` | Loads `.env` into a tidy `Settings` object. |
| `schwab_session.py` | Token persistence + builds an authenticated client. |
| `auth_setup.py` | **Step 1.** One-time browser login → writes `token.json`. |
| `accounts.py` | **Step 2.** Prints balances and positions. |
| `place_order.py` | **Step 3.** Places a limit order. |
| `token.json` | Cached OAuth tokens (auto-created). **Gitignored.** |

---

## 📱 Running on Google Colab (mobile-friendly, no laptop needed)

If you're on a phone/Colab, skip the scripts below and use the notebook
**`schwab_colab.ipynb`** instead — it's self-contained and walks you through
each step in cells.

**Open it directly in Colab** (replace nothing — this repo's path is baked in):

```
https://colab.research.google.com/github/caleblschulte0-ux/schwab-trader/blob/claude/schwab-trading-integration-wRfeP/schwab_colab.ipynb
```

Then run the cells top to bottom:
1. Install + paste your App Key/Secret (hidden input — nothing is saved to the file).
2. Tap the login URL → approve in your browser.
3. Paste the `https://127.0.0.1/?code=...` URL back → saves `token.json`.
4. View balances & positions.
5. Place a test limit order (priced so it won't fill).

> Colab wipes files when the runtime resets, so `token.json` won't persist
> forever there. The notebook's last cell explains how to reconnect, and you
> can mount Google Drive to keep tokens across sessions.

The rest of this README covers the **command-line scripts** (for running on a
regular computer).

---

## One-time setup

### 1. Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
```

### 2. Add your credentials

Your `.env` file is already created with your App Key, Secret, and callback
URL. If you ever need to recreate it:

```bash
cp .env.example .env
# then edit .env and paste your real values
```

`.env` and `token.json` are listed in `.gitignore`, so they will **never** be
committed.

> 🔐 **Security:** anyone with your App Key + Secret can trade on your account.
> If they're ever exposed (e.g. pasted into a chat or pushed to GitHub),
> regenerate the secret in the
> [Schwab Developer Portal](https://developer.schwab.com).

> ℹ️ Your callback URL must **exactly** match what's registered for your app
> in the portal. We use `https://127.0.0.1`.

---

## Step 1 — Authenticate

```bash
python auth_setup.py
```

What happens:

1. The script prints an authorization URL. **Open it in your browser** and log
   in to Schwab, then approve the app.
2. Schwab redirects your browser to `https://127.0.0.1/?code=...`. **The page
   won't load** — nothing is running on `127.0.0.1`. That's expected and fine.
3. **Copy the entire URL** from your browser's address bar and paste it back
   into the script.
4. The script swaps that one-time `code` for an **access token** and a
   **refresh token**, and saves them to `token.json`.

You only do this when your refresh token expires.

**Token lifetimes (important):**

- **Access token** — ~30 minutes. Used on every API call. The code refreshes
  it automatically and silently using the refresh token.
- **Refresh token** — ~7 days. When it expires, API calls start failing and
  you'll be told to **re-run `python auth_setup.py`**.

> The `code` in the redirect URL is only valid for ~30 seconds, so paste it
> promptly. If it expires, just run the script again.

---

## Step 2 — Balances & positions

```bash
python accounts.py
```

Example output:

```
Found 1 account(s).

================================================================
Account 12345678  (MARGIN)
================================================================
Balances:
  Total account value   $25,431.12
  Cash balance          $5,000.00
  Buying power          $10,000.00
  ...

Positions (2):
  SYMBOL           QTY     AVG PRICE       MKT VALUE       DAY P/L
  --------------------------------------------------------------
  AAPL              10       $180.50       $1,852.00        $17.00
  MSFT               5       $410.20       $2,075.50       -$5.50
```

---

## Step 3 — Place a limit order

A **limit order** only fills at your price *or better*:

- **BUY limit** → fills at or **below** your limit price.
- **SELL limit** → fills at or **above** your limit price.

```bash
# BUY 1 share of AAPL, only if it's $185.00 or lower
python place_order.py BUY AAPL 1 185.00

# SELL 1 share of AAPL at $999 (a price it won't reach — safe for testing)
python place_order.py SELL AAPL 1 999.00

# Skip the confirmation prompt (for scripts)
python place_order.py BUY AAPL 1 185.00 --yes

# Choose a specific account when you have more than one
python place_order.py BUY AAPL 1 185.00 --account 12345678
```

By default the script shows a summary and asks you to type `yes` before
sending. Orders are **DAY** orders (expire at market close if unfilled).

> 💡 The account number shown in the Schwab app is **not** what the API uses —
> it needs an encrypted "hash". The script fetches and maps this for you
> automatically.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No saved tokens found...` | Run `python auth_setup.py` first. |
| `Could not refresh your access token...` | Refresh token expired (~7 days). Re-run `auth_setup.py`. |
| `Token exchange failed` | The `code` expired (re-run), or the callback URL / keys don't match the portal. |
| `Account ... not found` | Use a number from `accounts.py`, or omit `--account`. |
| Order rejected by Schwab | Check market hours, buying power, and that the symbol is tradable. |

---

## Where to go next

The `SchwabClient` exposes much more than this starter uses:

- `client.get_quotes("AAPL")` — live quotes
- `client.get_orders(...)`, `client.cancel_order(...)` — manage open orders
- `client.create_market_order(...)`, `create_stop_order(...)`,
  `create_bracket_order(...)` — other order types
- `client.get_price_history(...)`, `get_option_chain(...)` — market data

Build on `schwab_session.get_client()` to reuse the authenticated session.
