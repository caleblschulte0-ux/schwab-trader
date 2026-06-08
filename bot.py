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
signals/holdings.json. The brain reads that file to know what it actually owns.
The brain's structured top-of-funnel (signals/candidates.json) is built SEPARATELY
by candidates.py, which runs on the brain's schedule (gather -> think -> emit picks);
the trader no longer gathers market data — it only reads orders.json + Schwab quotes
and executes, so it can run fast (every few minutes) without burning data-API budget.
A brain-written signals/watchlist.json lets the bot auto-enter on a price/date
trigger between brain runs (same guardrails); the bot only reads that file.

Options (paper-only for now): the brain may also buy LONG PUTS — defined-risk only
(max loss = the premium paid). Hard-enforced in code: long puts ONLY (buy_to_open;
no calls, no selling-to-open, no spreads, no shorts), premium*100*contracts <=
MAX_DOLLARS_PER_OPTION, underlying must clear the $MIN_SHARE_PRICE floor. A real
option order is NEVER placed unless BOTH DRY_RUN=false AND OPTIONS_LIVE=true.

Risk rules still enforced in code (your one rule is safe):
  * BUY-only; we only ever SELL shares/contracts we already own (never short).
  * stock: quantity * entry <= MAX_DOLLARS_PER_TRADE; put: premium*100*qty <= MAX_DOLLARS_PER_OPTION.
  * reject sub-$MIN_SHARE_PRICE penny stocks / underlyings (pump/dump guard).
  * skip symbols already HELD, with an OPEN buy, OR bought in the last
    RECENT_BUY_COOLDOWN_MIN minutes (closes the settlement-lag double-buy gap);
    if orders can't be read, place NOTHING (fail safe).
  * don't chase (hard backstop): skip a BUY if live ask > limit_price * (1+MAX_SLIPPAGE).

DRY_RUN defaults to "true". Set a DRY_RUN repo variable to "false" to go live.

Secrets (GitHub Actions): SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_REFRESH_TOKEN
Optional: SCHWAB_CALLBACK_URL, DRY_RUN
(Market-data keys FMP_API_KEY / ALPHA_API_KEY now live in candidates.py, not here.)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from schwab import SchwabAuth, SchwabClient
from schwab.models.generated.trading_models import Instruction, Duration

# ===== GUARDRAILS / KNOBS =====
MAX_DOLLARS_PER_TRADE = 150.00  # never spend more than this on one STOCK entry (was 65; bumped to deploy more of the $1k book ~6 full positions)
MAX_DOLLARS_PER_OPTION = 100.00 # never RISK more than this on one long-put bet (premium*100*contracts)
OPTION_MULTIPLIER     = 100      # shares per option contract (premium is per-share)
MAX_SIGNAL_AGE_HOURS  = 18      # ignore a stale orders.json
MAX_SLIPPAGE          = 0.05    # skip a BUY if live ask is >5% above the pick's limit
MARKETABLE_BUFFER     = 0.002   # buy limit = live ask * (1 + this) so it fills now
ORDERS_FILE           = "signals/orders.json"
HOLDINGS_FILE         = "signals/holdings.json"
MIN_TP_OVER_ENTRY     = 0.005
MIN_STOP_UNDER_ENTRY  = 0.005
MIN_SHARE_PRICE       = 2.00    # hard floor: skip sub-$2 penny-stock pump/dump traps
RECENT_BUY_COOLDOWN_MIN = 60    # don't re-buy a symbol bought in the last hour
WATCHLIST_FILE        = "signals/watchlist.json"
CANDIDATES_FILE       = "signals/candidates.json"  # read-only here: ENTRY ATTRIBUTION only (see _entry_meta)
SELL_ORDERS_FILE      = "signals/sell_orders.json"  # SELL decisions from the sell brain (router-approved / urgent)
# --- paper trading (DRY_RUN): a simulated book so the brain has MEMORY of what it
#     "owns" (kills the re-pick/averaging-down churn) AND we get a real P/L scorecard. ---
PAPER_ACCOUNT_FILE    = "signals/paper_account.json"   # simulated cash + positions + closed trades
PAPER_LEDGER_FILE     = "reports/paper_ledger.md"      # human-readable running P/L log
PAPER_START_EQUITY    = 1000.00                         # paper trading capital (bumped 400 -> 1000)
# --- watchlist (bot auto-enters when a brain-set trigger fires between runs) ---
MAX_WATCHLIST           = 12    # cap watch items (bounds per-symbol quote calls)
MAX_WATCHLIST_AGE_HOURS = 48    # ignore a watchlist file older than this (fail-safe)
# ==============================

APP_KEY       = os.environ["SCHWAB_APP_KEY"].strip()
APP_SECRET    = os.environ["SCHWAB_APP_SECRET"].strip()
REFRESH_TOKEN = os.environ["SCHWAB_REFRESH_TOKEN"].strip()
CALLBACK      = os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1/").strip()
DRY_RUN       = os.environ.get("DRY_RUN", "true").strip().lower() != "false"
# SECOND, independent gate for OPTIONS: long puts stay PAPER-ONLY until this is
# explicitly turned on — so even with DRY_RUN=false (stocks live), no REAL option
# order is ever placed unless OPTIONS_LIVE=true too. Defined-risk puts only, always.
OPTIONS_LIVE  = os.environ.get("OPTIONS_LIVE", "false").strip().lower() == "true"


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


def load_orders() -> tuple[str | None, list[dict], dict]:
    if not os.path.exists(ORDERS_FILE):
        print(f"No {ORDERS_FILE} found.")
        return None, [], {}
    with open(ORDERS_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("generated_utc"), data.get("orders", []) or [], data.get("funnel") or {}


def load_sell_orders() -> set[str]:
    """Symbols the SELL pipeline wants closed — `signals/sell_orders.json`, written by
    route_sells.py after the sell brain (autonomous, urgent, or human-approved). This is
    the ONLY price-independent exit path now: a position is HELD until this file (or a
    legacy orders.json SELL) names it. Fresh-guarded so a stale file can't fire an old
    SELL on a re-bought name. Any read problem returns an empty set (fail-safe: no sells)."""
    if not os.path.exists(SELL_ORDERS_FILE):
        return set()
    try:
        with open(SELL_ORDERS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not read sell orders: {exc}")
        return set()
    if not is_fresh(data.get("generated_utc")):
        print("(info) sell_orders.json is stale — ignoring.")
        return set()
    out = {str(o.get("symbol", "")).strip().upper()
           for o in (data.get("sells") or []) if o.get("symbol")}
    if out:
        print(f"Sell pipeline wants closed: {', '.join(sorted(out))}")
    return out


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


def _market_tz():
    """US market timezone (handles EDT/EST automatically); falls back to UTC."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:  # noqa: BLE001 - some hosts lack tz data; degrade to UTC
        return timezone.utc


# Operating window = the US regular session (09:30-16:00 ET) widened by a buffer on
# each side. With the default 60-min buffer the executor is active 08:30-17:00 ET —
# i.e. 1 hour before the open through 1 hour after the close. Tune the buffer here.
SESSION_BUFFER_MIN = 60


def in_trading_window(now: datetime | None = None) -> bool:
    """True during the executor's operating window: the US regular session
    (09:30-16:00 ET) PLUS SESSION_BUFFER_MIN on each side — so 08:30-17:00 ET with the
    default 60-min buffer — Mon-Fri, DST-aware. The trader acts ONLY in this window,
    regardless of when the external cron pokes it. (Market holidays aren't modeled; a
    weekday holiday simply no-ops at the broker.)"""
    et = (now or datetime.now(timezone.utc)).astimezone(_market_tz())
    if et.weekday() >= 5:  # Sat/Sun
        return False
    cur = et.hour * 60 + et.minute
    open_min = 9 * 60 + 30 - SESSION_BUFFER_MIN   # 08:30 ET with the default buffer
    close_min = 16 * 60 + SESSION_BUFFER_MIN      # 17:00 ET with the default buffer
    return open_min <= cur <= close_min


def get_positions(client: SchwabClient) -> dict[str, dict]:
    if DRY_RUN:  # paper book is the source of truth in dry-run (real account untouched)
        return paper_positions_as_holdings(_PAPER or {})
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


def write_holdings(positions: dict, marks: dict | None = None) -> None:
    """Write the account's REAL holdings to a file the brain trusts as ground truth.
    ENRICHED with `opened_utc` + a current `last` mark + `unrealized_pct` + `value` so the
    SELL ROUTER (route_sells.py) can classify a holding as long-held / top-winner / over-
    sized WITHOUT needing live quotes of its own. The buy brain ignores the extra fields.
    `marks` is {symbol: last_price}; opened_utc comes from the paper book (None when live)."""
    marks = marks or {}
    paper_pos = (_PAPER or {}).get("positions", {}) if DRY_RUN else {}
    rows = []
    for s, p in sorted(positions.items()):
        avg = p["avg"]
        qty = p["qty"]
        mult = p.get("multiplier", 1)
        row = {"symbol": s, "quantity": qty, "avg_price": avg}
        opened = paper_pos.get(s, {}).get("opened_utc")
        if opened:
            row["opened_utc"] = opened
        last = marks.get(s)
        if last:
            row["last"] = round(last, 4)
            row["unrealized_pct"] = round((last / avg - 1) * 100, 2) if avg else None
            row["value"] = round(qty * last * mult, 2)
        rows.append(row)
    data = {"updated_utc": datetime.now(timezone.utc).isoformat(), "holdings": rows}
    try:
        os.makedirs(os.path.dirname(HOLDINGS_FILE), exist_ok=True)
        with open(HOLDINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        print(f"Wrote {HOLDINGS_FILE}: {len(rows)} holding(s)")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not write holdings file: {exc}")


# ============================ PAPER-TRADING ENGINE ============================
# Active ONLY in DRY_RUN. Persists a simulated book to PAPER_ACCOUNT_FILE so that
# holdings.json reflects what the brain "owns" on paper — giving the brain the
# MEMORY it was missing (it stops re-buying / chasing a name it already holds) —
# and so we accumulate a real running P/L scorecard in PAPER_LEDGER_FILE.
_PAPER: dict | None = None   # loaded in main() when DRY_RUN; mutated by buy()/sell()

# Entry ATTRIBUTION (read-only): candidates.json gives each symbol its signal tag(s)
# + catalyst freshness + the macro tape. Captured at BUY time and carried onto the
# closed trade so analyze.py can tell which SIGNALS actually make money. Purely
# additive instrumentation — wrapped so a failure here can NEVER affect a trade.
_CANDIDATES_BY_SYM: dict[str, dict] = {}
_TAPE_TONE: str | None = None


def load_paper_account() -> dict:
    """Load the simulated book, or initialize a fresh one at PAPER_START_EQUITY."""
    if os.path.exists(PAPER_ACCOUNT_FILE):
        try:
            with open(PAPER_ACCOUNT_FILE, encoding="utf-8") as fh:
                st = json.load(fh)
            st.setdefault("cash", PAPER_START_EQUITY)
            st.setdefault("start_equity", PAPER_START_EQUITY)
            st.setdefault("positions", {})
            st.setdefault("realized_pnl", 0.0)
            st.setdefault("closed_trades", [])
            return st
        except Exception as exc:  # noqa: BLE001
            print(f"(warn) could not read paper account ({exc}) — starting fresh.")
    return {"cash": PAPER_START_EQUITY, "start_equity": PAPER_START_EQUITY,
            "positions": {}, "realized_pnl": 0.0, "closed_trades": []}


def save_paper_account(state: dict) -> None:
    state["updated_utc"] = datetime.now(timezone.utc).isoformat()
    try:
        os.makedirs(os.path.dirname(PAPER_ACCOUNT_FILE), exist_ok=True)
        with open(PAPER_ACCOUNT_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not write paper account: {exc}")


def paper_positions_as_holdings(state: dict) -> dict:
    """Shape the paper book like get_positions() output so the rest of main() and
    write_holdings() treat paper positions exactly like real ones. Carries `kind`/
    `multiplier` so the exit loop knows to close a put with sell_option (not sell)."""
    return {s: {"qty": p["qty"], "avg": p["entry"],
                "kind": p.get("kind", "stock"), "multiplier": p.get("multiplier", 1)}
            for s, p in (state.get("positions") or {}).items()}


def paper_blocked(state: dict) -> set:
    """No-rebuy set for paper: a symbol CLOSED within the cooldown window — stops the
    brain from instantly re-buying a name it just stopped out of (held names are
    already blocked by the 'already holding' check)."""
    blocked: set[str] = set()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=RECENT_BUY_COOLDOWN_MIN)
    for t in state.get("closed_trades", []):
        closed = _parse_dt(t.get("closed_utc"))
        if closed is not None and closed >= cutoff:
            blocked.add(t.get("symbol"))
    return blocked


def paper_record_buy(sym: str, qty: int, price: float, tp, sl, *,
                     kind: str = "stock", multiplier: int = 1, occ=None,
                     underlying=None, option_type=None, strike=None,
                     expiration=None, meta: dict | None = None) -> None:
    """Simulate a fill: deduct cash, open a position carrying its OWN tp/sl so the
    bot can manage the exit even after the brain drops the name from orders.json.
    For options, `multiplier` is OPTION_MULTIPLIER (100) and `price` is the per-share
    premium, so cost = qty(contracts) * premium * 100; option metadata is stored too."""
    if _PAPER is None:
        return
    while qty > 0 and qty * price * multiplier > _PAPER["cash"]:   # respect available paper cash
        qty -= 1
    if qty <= 0:
        print(f"[{sym}] PAPER: insufficient cash (${_PAPER['cash']:.2f}) — no fill")
        return
    cost = qty * price * multiplier
    _PAPER["cash"] -= cost
    pos = {
        "qty": qty, "entry": round(price, 4),
        "tp": tp, "sl": sl,
        "kind": kind, "multiplier": multiplier,
        "opened_utc": datetime.now(timezone.utc).isoformat(),
    }
    if meta:  # entry attribution (signal/catalyst/tape) — carried to the closed trade
        pos["meta"] = meta
    if kind != "stock":  # carry the contract details for the ledger / EOD breakdown
        pos.update({"occ": occ, "underlying": underlying, "option_type": option_type,
                    "strike": strike, "expiration": expiration})
    _PAPER["positions"][sym] = pos
    unit = "contract(s)" if kind != "stock" else "sh"
    print(f"[{sym}] PAPER FILL: BUY {qty} {unit} @ ${price:.2f} = ${cost:.2f} "
          f"(cash left ${_PAPER['cash']:.2f})")


def paper_record_sell(sym: str, price: float, why: str) -> None:
    """Simulate a close: credit proceeds, book realized P/L, log the closed trade."""
    if _PAPER is None:
        return
    pos = _PAPER["positions"].pop(sym, None)
    if not pos:
        return
    qty = pos["qty"]
    mult = pos.get("multiplier", 1)            # 100 for options, 1 for stock
    proceeds = qty * price * mult
    pnl = (price - pos["entry"]) * qty * mult
    pnl_pct = (price / pos["entry"] - 1) * 100 if pos["entry"] else 0.0
    _PAPER["cash"] += proceeds
    _PAPER["realized_pnl"] += pnl
    closed_dt = datetime.now(timezone.utc)
    opened_dt = _parse_dt(pos.get("opened_utc"))
    hold_h = round((closed_dt - opened_dt).total_seconds() / 3600, 2) if opened_dt else None
    trade = {
        "symbol": sym, "qty": qty, "kind": pos.get("kind", "stock"), "multiplier": mult,
        "entry": round(pos["entry"], 4),
        "exit": round(price, 4), "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
        "opened_utc": pos.get("opened_utc"),
        "closed_utc": closed_dt.isoformat(), "reason": why,
        "hold_h": hold_h,
    }
    meta = pos.get("meta") or {}   # entry attribution captured at BUY time (may be absent on old positions)
    for k in ("signals", "catalyst_age_h", "market_cap", "volume",
              "ref_price", "entry_ask", "entry_last", "tape_tone"):
        if k in meta:
            trade[k] = meta[k]
    _PAPER["closed_trades"].append(trade)
    unit = "contract(s)" if pos.get("kind", "stock") != "stock" else "sh"
    print(f"[{sym}] PAPER CLOSE: SELL {qty} {unit} @ ${price:.2f} → P/L ${pnl:+.2f} "
          f"({pnl_pct:+.1f}%) [{why}]")


def write_paper_ledger(state: dict, marks: dict) -> None:
    """Human-readable running scorecard: open book (mark-to-market), realized P/L,
    equity vs. start, and the most recent closed trades."""
    pos = state.get("positions") or {}
    unreal = 0.0
    rows = []
    for s, p in sorted(pos.items()):
        mult = p.get("multiplier", 1)
        last = marks.get(s) or p["entry"]
        u = (last - p["entry"]) * p["qty"] * mult   # ×100 for options
        unreal += u
        rows.append(f"| {s} | {p.get('kind', 'stock')} | {p['qty']} | ${p['entry']:.2f} | ${last:.2f} | "
                    f"${p.get('tp') or 0:.2f} | ${p.get('sl') or 0:.2f} | ${u:+.2f} |")
    invested = sum(p["entry"] * p["qty"] * p.get("multiplier", 1) for p in pos.values())
    equity = state["cash"] + sum((marks.get(s) or p["entry"]) * p["qty"] * p.get("multiplier", 1)
                                 for s, p in pos.items())
    realized = state.get("realized_pnl", 0.0)
    total_ret = equity - state["start_equity"]
    closed = state.get("closed_trades", [])
    wins = [t for t in closed if t.get("pnl", 0) > 0]
    winrate = (100 * len(wins) / len(closed)) if closed else 0.0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Paper-Trading Ledger (DRY_RUN)", "",
        f"_Updated {now}_", "",
        f"**Equity:** ${equity:.2f}  (start ${state['start_equity']:.2f}, "
        f"**{total_ret:+.2f} / {100*total_ret/state['start_equity']:+.1f}%**)  ",
        f"**Cash:** ${state['cash']:.2f}   **Invested:** ${invested:.2f}   "
        f"**Open positions:** {len(pos)}  ",
        f"**Realized P/L:** ${realized:+.2f}   **Unrealized:** ${unreal:+.2f}   "
        f"**Closed trades:** {len(closed)}   **Win rate:** {winrate:.0f}%", "",
        "## Open positions  _(option Entry/Last = per-share premium; Unrealized is the real $ P/L, ×100/contract)_", "",
        "| Symbol | Kind | Qty | Entry | Last | TP | SL | Unrealized |",
        "|--------|------|-----|-------|------|----|----|------------|",
    ]
    lines += rows or ["| _none_ | | | | | | | |"]
    lines += ["", "## Last 15 closed trades", "",
              "| Symbol | Kind | Qty | Entry | Exit | P/L | % | Reason | Closed |",
              "|--------|------|-----|-------|------|-----|---|--------|--------|"]
    for t in closed[-15:][::-1]:
        lines.append(f"| {t['symbol']} | {t.get('kind', 'stock')} | {t['qty']} | ${t['entry']:.2f} | "
                     f"${t['exit']:.2f} | ${t['pnl']:+.2f} | {t['pnl_pct']:+.1f}% | "
                     f"{t.get('reason','')} | {str(t.get('closed_utc',''))[:16]} |")
    if not closed:
        lines.append("| _none yet_ | | | | | | | | |")
    try:
        os.makedirs(os.path.dirname(PAPER_LEDGER_FILE), exist_ok=True)
        with open(PAPER_LEDGER_FILE, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"Wrote {PAPER_LEDGER_FILE}: equity ${equity:.2f} "
              f"({total_ret:+.2f}), {len(pos)} open, {len(closed)} closed")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not write paper ledger: {exc}")
# ========================== END PAPER-TRADING ENGINE =========================


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
    if DRY_RUN:  # paper cooldown: don't instantly re-buy a name just closed/stopped
        return paper_blocked(_PAPER or {}), True
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


def load_candidates_index() -> tuple[dict[str, dict], str | None]:
    """Read signals/candidates.json (written by candidates.py) into {SYMBOL: row}
    plus the macro tape `tone`, for ENTRY ATTRIBUTION only. Read-only and best-effort:
    any problem returns ({}, None). Attribution is a nice-to-have that must never
    affect trading; the trader does not otherwise depend on this file."""
    try:
        with open(CANDIDATES_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:  # noqa: BLE001 - missing/corrupt -> no attribution, no harm
        return {}, None
    by_sym: dict[str, dict] = {}
    for row in (data.get("candidates") or []):
        sym = str(row.get("symbol", "")).strip().upper()
        if sym:
            by_sym[sym] = row
    tone = (data.get("market") or {}).get("tone")
    return by_sym, tone


def _entry_meta(sym: str, ref_price, q: dict | None) -> dict:
    """Build the attribution record captured at BUY time: the entry SIGNAL tag(s),
    catalyst freshness (hours), size context, the brain's intended price (for slippage
    analysis), the live ask/last at the fill, and the macro tape. Fully defensive —
    every field degrades to None and any exception yields {} so this instrumentation
    can NEVER block or alter a trade."""
    try:
        row = _CANDIDATES_BY_SYM.get(str(sym).upper(), {})
        cat = row.get("catalyst") or {}
        pub = _parse_dt(cat.get("published_utc"))
        age_h = round((datetime.now(timezone.utc) - pub).total_seconds() / 3600, 2) if pub else None
        q = q or {}
        return {
            "signals": row.get("signals") or ([row["signal"]] if row.get("signal") else []),
            "catalyst_age_h": age_h,
            "market_cap": row.get("market_cap"),
            "volume": row.get("volume"),
            "ref_price": round(float(ref_price), 4) if ref_price else None,
            "entry_ask": live_ask(q),
            "entry_last": live_last(q),
            "tape_tone": _TAPE_TONE,
        }
    except Exception:  # noqa: BLE001 - attribution must never break a trade
        return {}


def build_occ_symbol(underlying, expiration, option_type, strike) -> str | None:
    """Schwab/OCC option symbol: 6-char underlying (right-space-padded) + YYMMDD +
    C/P + strike*1000 as 8 digits. e.g. ('AAPL','2025-01-17','put',150) ->
    'AAPL  250117P00150000'. Returns None if any field is unusable."""
    try:
        d = datetime.fromisoformat(str(expiration)[:10]).strftime("%y%m%d")
        cp = "P" if str(option_type).lower().startswith("p") else "C"
        strike_int = int(round(float(strike) * 1000))
    except (ValueError, TypeError):
        return None
    if strike_int <= 0 or not underlying:
        return None
    return f"{str(underlying).upper():<6}{d}{cp}{strike_int:08d}"


def _validate_option_pick(order: dict) -> tuple[bool, str]:
    """Long-PUT defined-risk gate. ONLY long puts (buy_to_open); max loss = premium *
    100 * contracts must clear MAX_DOLLARS_PER_OPTION; anything else is rejected."""
    if str(order.get("option_type", "")).lower() != "put":
        return False, "only long PUTS supported (no calls/sell-to-open/spreads/shorts)"
    underlying = order.get("underlying")
    strike = order.get("strike") or 0
    contracts = order.get("contracts") or 0
    premium = order.get("limit_price") or 0   # per-share premium the brain expects to pay
    tp = order.get("take_profit") or 0
    sl = order.get("stop_loss") or 0
    if not underlying:
        return False, "missing underlying"
    if strike <= 0:
        return False, "bad strike"
    try:
        edate = datetime.fromisoformat(str(order.get("expiration"))[:10]).date()
    except (ValueError, TypeError):
        return False, "bad/missing expiration (need YYYY-MM-DD)"
    if edate < datetime.now(timezone.utc).date():
        return False, "expiration is in the past"
    if contracts < 1:
        return False, "contracts must be >= 1"
    if premium <= 0:
        return False, "bad limit_price (premium per share)"
    cost = premium * OPTION_MULTIPLIER * contracts
    if cost > MAX_DOLLARS_PER_OPTION:
        return False, f"max risk ${cost:.0f} > ${MAX_DOLLARS_PER_OPTION:.0f} put cap"
    # tp/sl are OPTIONAL now — the SELL BRAIN manages exits by judgment, not pre-set levels.
    # If the brain still supplies them, sanity-check the sides (long put: tp>entry, sl<entry).
    if (tp and sl) and (tp < premium * (1 + MIN_TP_OVER_ENTRY) or sl > premium * (1 - MIN_STOP_UNDER_ENTRY)):
        return False, "tp/stop not on correct sides of premium (long put: tp>entry, sl<entry)"
    return True, "ok"


def validate_pick(order: dict) -> tuple[bool, str]:
    if order.get("action") != "BUY":
        return False, "not a BUY"
    instr = order.get("instrument", "stock")
    if instr == "option":
        return _validate_option_pick(order)
    if instr != "stock":
        return False, "only stocks/options supported"
    qty = order.get("quantity") or 0
    limit = order.get("limit_price") or 0
    tp = order.get("take_profit") or 0
    sl = order.get("stop_loss") or 0
    if qty <= 0 or limit <= 0:
        return False, "bad quantity/limit_price"
    if limit < MIN_SHARE_PRICE:
        return False, f"under ${MIN_SHARE_PRICE:.0f} price floor (penny-stock guard)"
    # tp/sl are OPTIONAL now — the SELL BRAIN manages exits by judgment, not pre-set levels.
    # If the brain still supplies them, sanity-check the sides (tp above / sl below entry).
    if (tp and sl) and (tp < limit * (1 + MIN_TP_OVER_ENTRY) or sl > limit * (1 - MIN_STOP_UNDER_ENTRY)):
        return False, "tp/stop not on correct sides of entry"
    return True, "ok"


def buy(client, acct, sym: str, qty: int, limit: float, tp=None, sl=None, meta=None):
    if DRY_RUN:
        paper_record_buy(sym, qty, limit, tp, sl, meta=meta)  # simulate the fill into the paper book
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
        paper_record_sell(sym, limit, why)  # simulate the close + book P/L
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


def _build_option_order(occ: str, contracts: int, premium: float, instruction, effect):
    """Hand-build a single-leg OPTION limit Order (the library has no convenience
    method for options). Lazy-imported so a library-version mismatch can never break
    module import or the stock path. instruction = buy_to_open / sell_to_close."""
    from decimal import Decimal
    from schwab.models.generated.trading_models import (
        Order, OrderLegCollection, OrderType, OrderStrategyType,
        ComplexOrderStrategyType, OrderLegType, PositionEffect, QuantityType)
    eff = PositionEffect.opening if effect == "opening" else PositionEffect.closing
    return Order(
        order_type=OrderType.limit,
        duration=Duration.day,
        order_strategy_type=OrderStrategyType.single,
        complex_order_strategy_type=ComplexOrderStrategyType.none,
        price=Decimal(str(round(premium, 2))),
        quantity=Decimal(str(contracts)),
        order_leg_collection=[OrderLegCollection(
            order_leg_type=OrderLegType.option, leg_id=1,
            instrument={"symbol": occ, "assetType": "OPTION"},
            instruction=instruction, position_effect=eff,
            quantity=Decimal(str(contracts)), quantity_type=QuantityType.shares)])


def buy_option(client, acct, occ: str, contracts: int, premium: float, *,
               underlying=None, option_type="put", strike=None, expiration=None,
               tp=None, sl=None, meta=None):
    """Buy-to-open a long put. Paper by default. A REAL order fires ONLY when
    DRY_RUN=false AND OPTIONS_LIVE=true (the second gate keeps options paper-only
    until deliberately enabled, even after stocks go live)."""
    if DRY_RUN:
        paper_record_buy(occ, contracts, premium, tp, sl, kind=option_type or "put",
                         multiplier=OPTION_MULTIPLIER, occ=occ, underlying=underlying,
                         option_type=option_type, strike=strike, expiration=expiration,
                         meta=meta)
        return
    if not OPTIONS_LIVE:
        print(f"[{occ}] OPTIONS_LIVE off — real option order suppressed (paper-only by design).")
        return
    try:
        order = _build_option_order(occ, contracts, premium, Instruction.buy_to_open, "opening")
        client.place_order(acct.hash_value, order)
        print(f"[{occ}] ✅ LIVE BUY_TO_OPEN {contracts} @ ${premium:.2f} (marketable limit)")
    except Exception as exc:  # noqa: BLE001
        print(f"[{occ}] option buy error: {exc}")


def sell_option(client, acct, occ: str, contracts: int, premium: float, why: str):
    """Sell-to-close a long put. Paper by default; real order only behind both gates."""
    if DRY_RUN:
        paper_record_sell(occ, premium, why)
        return
    if not OPTIONS_LIVE:
        print(f"[{occ}] OPTIONS_LIVE off — real option close suppressed (paper-only by design).")
        return
    try:
        order = _build_option_order(occ, contracts, premium, Instruction.sell_to_close, "closing")
        client.place_order(acct.hash_value, order)
        print(f"[{occ}] ✅ LIVE SELL_TO_CLOSE {contracts} @ ${premium:.2f} ({why})")
    except Exception as exc:  # noqa: BLE001
        print(f"[{occ}] option sell error: {exc}")


def load_watchlist() -> list[dict]:
    """Brain-written names to auto-enter when a trigger fires between brain runs.
    The bot only READS this file (the brain owns it). Returns [] on any problem
    or if the file is stale (fail-safe — never act on an abandoned watchlist)."""
    if not os.path.exists(WATCHLIST_FILE):
        return []
    try:
        with open(WATCHLIST_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not read watchlist: {exc}")
        return []
    gen = _parse_dt(data.get("generated_utc"))
    if gen is not None:
        age_h = (datetime.now(timezone.utc) - gen).total_seconds() / 3600
        if age_h > MAX_WATCHLIST_AGE_HOURS:
            print(f"(info) watchlist is stale ({age_h:.0f}h > {MAX_WATCHLIST_AGE_HOURS}h) — ignoring.")
            return []
    return (data.get("watch") or [])[:MAX_WATCHLIST]


def watch_triggered(w: dict, q: dict) -> tuple[bool, str]:
    """Has this watch item's entry condition fired? breakout: live >= trigger_price;
    pullback: live <= trigger_price; date: today >= trigger_date."""
    trig = str(w.get("trigger", "")).lower()
    tp = w.get("trigger_price")
    last = live_last(q)
    if trig == "breakout":
        if last and tp and last >= tp:
            return True, f"broke ${tp} (last ${last})"
        return False, f"awaiting breakout > ${tp} (last ${last})"
    if trig == "pullback":
        if last and tp and last <= tp:
            return True, f"pulled back to ${tp} (last ${last})"
        return False, f"awaiting pullback <= ${tp} (last ${last})"
    if trig == "date":
        td = str(w.get("trigger_date") or w.get("good_until") or "")[:10]
        try:
            ok = datetime.now(timezone.utc).date() >= datetime.fromisoformat(td).date()
        except ValueError:
            return False, "bad trigger_date"
        return (ok, f"on/after {td}") if ok else (False, f"waiting for {td}")
    return False, f"unknown trigger '{trig}'"


def try_enter(client, acct, sym: str, want_qty, ref_limit: float,
              positions: dict, blocked: set, bought: set, q: dict | None = None,
              tp=None, sl=None) -> None:
    """Shared entry path for BOTH orders.json picks and watchlist triggers: dedupe,
    price off the LIVE ask, enforce the slippage backstop + $150 cap, then buy. The
    watchlist path passes the quote it already pulled (q) to avoid re-quoting."""
    if sym in positions:
        print(f"[{sym}] SKIP — already holding")
        return
    if sym in blocked:
        print(f"[{sym}] SKIP — open or recent buy order (no double-buy)")
        return
    if sym in bought:
        print(f"[{sym}] SKIP — already bought this run")
        return
    if q is None:
        q = quote(client, sym)
    ask = live_ask(q)
    if not ask:
        print(f"[{sym}] SKIP — no live quote")
        return
    if ask > ref_limit * (1 + MAX_SLIPPAGE):
        print(f"[{sym}] SKIP — ran away: live ask ${ask:.2f} > limit ${ref_limit:.2f} +{MAX_SLIPPAGE*100:.0f}%")
        return
    entry = round(ask * (1 + MARKETABLE_BUFFER), 2)  # marketable limit at the live ask
    qty = int(want_qty)
    while qty > 0 and qty * entry > MAX_DOLLARS_PER_TRADE:  # re-check cap on real price
        qty -= 1
    if qty <= 0:
        print(f"[{sym}] SKIP — 1 share at ${entry:.2f} exceeds ${MAX_DOLLARS_PER_TRADE:.0f} cap")
        return
    meta = _entry_meta(sym, ref_limit, q)  # attribution only — does not affect the order
    buy(client, acct, sym, qty, entry, tp=tp, sl=sl, meta=meta)
    bought.add(sym)


def try_enter_option(client, acct, pick: dict, positions: dict, blocked: set,
                     bought: set) -> None:
    """Entry path for a long-PUT pick: build the OCC symbol, enforce the underlying's
    $MIN_SHARE_PRICE floor (no penny-stock puts), price off the OPTION's live ask,
    trim contracts to the MAX_DOLLARS_PER_OPTION defined-risk cap, then buy_option.
    Dedupe + slippage backstop mirror the stock path. Keyed by the OCC symbol."""
    underlying = pick.get("underlying", "?")
    occ = build_occ_symbol(underlying, pick.get("expiration"),
                           pick.get("option_type"), pick.get("strike"))
    if not occ:
        print(f"[{underlying}] option SKIP — bad contract spec (strike/expiration)")
        return
    if occ in positions:
        print(f"[{occ}] SKIP — already holding")
        return
    if occ in blocked:
        print(f"[{occ}] SKIP — recent close (no immediate re-buy)")
        return
    if occ in bought:
        print(f"[{occ}] SKIP — already bought this run")
        return
    uq = quote(client, underlying)              # penny-stock floor on the UNDERLYING
    ulast = live_last(uq)
    if ulast and ulast < MIN_SHARE_PRICE:
        print(f"[{occ}] SKIP — underlying ${ulast:.2f} under ${MIN_SHARE_PRICE:.0f} floor")
        return
    q = quote(client, occ)                      # price off the OPTION's live ask
    ask = live_ask(q)
    if not ask:
        print(f"[{occ}] SKIP — no live option quote (contract may not exist / illiquid)")
        return
    ref = float(pick.get("limit_price") or 0)
    if ref and ask > ref * (1 + MAX_SLIPPAGE):
        print(f"[{occ}] SKIP — ran away: ask ${ask:.2f} > limit ${ref:.2f} +{MAX_SLIPPAGE*100:.0f}%")
        return
    entry = round(ask * (1 + MARKETABLE_BUFFER), 2)   # marketable premium
    contracts = int(pick.get("contracts") or 1)
    while contracts > 0 and entry * OPTION_MULTIPLIER * contracts > MAX_DOLLARS_PER_OPTION:
        contracts -= 1
    if contracts <= 0:
        print(f"[{occ}] SKIP — 1 contract (${entry*OPTION_MULTIPLIER:.0f}) exceeds "
              f"${MAX_DOLLARS_PER_OPTION:.0f} put cap")
        return
    meta = _entry_meta(underlying, ref or pick.get("limit_price"), q)  # attribution only
    buy_option(client, acct, occ, contracts, entry, underlying=underlying,
               option_type=pick.get("option_type"), strike=pick.get("strike"),
               expiration=pick.get("expiration"),
               tp=pick.get("take_profit"), sl=pick.get("stop_loss"), meta=meta)
    bought.add(occ)


def main() -> int:
    global _PAPER, _CANDIDATES_BY_SYM, _TAPE_TONE
    mode = "DRY-RUN (paper book)" if DRY_RUN else "LIVE (real orders!)"
    print(f"=== Executor | mode: {mode} ===")
    # MARKET-HOURS GUARD: the executor must NEVER run trading logic outside the US
    # regular session. The external cron can poke this workflow at any hour, so we
    # enforce it in CODE here — not just at the trigger — and no-op cleanly (before
    # even logging in to Schwab) when the market is closed. Override for a manual test
    # with IGNORE_MARKET_HOURS=true.
    if not in_trading_window() and os.environ.get("IGNORE_MARKET_HOURS", "").strip().lower() != "true":
        et = datetime.now(timezone.utc).astimezone(_market_tz())
        print(f"Outside trading window ({et:%a %H:%M} ET; active 08:30-17:00 ET) — "
              "executor no-op. (Set IGNORE_MARKET_HOURS=true to force a run.)")
        print("=== done ===")
        return 0
    if DRY_RUN:  # load the simulated book BEFORE get_positions() reads from it
        _PAPER = load_paper_account()
        print(f"Paper book: cash ${_PAPER['cash']:.2f}, "
              f"{len(_PAPER['positions'])} open, realized ${_PAPER['realized_pnl']:+.2f}")
    # Load the entry-attribution index (read-only; best-effort). Lets each fill record
    # WHY it was bought — signal tag, catalyst age, tape — for analyze.py to score.
    _CANDIDATES_BY_SYM, _TAPE_TONE = load_candidates_index()

    client = get_client()
    acct = client.get_account_numbers().accounts[0]
    positions = get_positions(client)
    # One live quote per held name, reused for: holdings enrichment, the exit sell price,
    # and the end-of-run paper mark-to-market (no double-quoting).
    marks = {s: live_last(quote(client, s)) for s in positions}
    marks = {s: m for s, m in marks.items() if m}
    write_holdings(positions, marks)  # enriched ground-truth holdings for the brain + sell router
    blocked, orders_ok = get_blocked_buy_symbols(client, acct.hash_value)
    print(f"Held: {', '.join(positions) or '(none)'} | No-rebuy: "
          f"{', '.join(blocked) or '(none)'} | read_ok={orders_ok}")

    generated_utc, orders, funnel = load_orders()
    fresh = bool(orders) and is_fresh(generated_utc)
    if funnel:  # the brain's funnel tally (proof of how wide it scanned)
        print(f"Funnel this run: {funnel}")

    # EXITS are now JUDGMENT-DRIVEN, not price-driven: there are NO pre-set take-profit /
    # stop-loss auto-exits anymore. A position is HELD until the SELL pipeline explicitly
    # names it — sell_orders.json (written by route_sells.py after the sell brain) or a
    # legacy orders.json SELL. This is what lets a future-AMD ride through a drawdown.
    brain_sells = load_sell_orders()
    if fresh:
        brain_sells |= {str(o.get("symbol")).strip().upper()
                        for o in orders if o.get("action") == "SELL" and o.get("symbol")}

    watch = load_watchlist()  # brain-set names to auto-enter on a trigger (used by entries below)

    # ---- EXITS: close ONLY what the sell pipeline asks for (judgment, not price). ----
    # Stocks close with sell(), long puts with sell_option() — dispatched on position kind.
    for sym, pos in positions.items():
        last = marks.get(sym)
        if sym in brain_sells:
            close = sell_option if pos.get("kind", "stock") != "stock" else sell
            close(client, acct, sym, int(pos["qty"]), last or pos["avg"], "sell brain")
        else:
            print(f"[{sym}] hold — last ${last if last else '?'}")

    # ---- ENTRIES: priced off the LIVE ask. Two sources: watchlist triggers
    #      (independent of orders freshness) and fresh BUY picks from orders.json.
    if not orders_ok:
        print("SKIP all entries — could not read existing orders (fail-safe).")
        print("=== done ===")
        return 0
    bought: set[str] = set()  # symbols entered THIS run (prevents double-buys across both paths)

    # A) WATCHLIST triggers — enter when the brain-set condition fires.
    for w in watch:
        sym = w.get("symbol", "?")
        gu = str(w.get("good_until") or "")[:10]
        if gu:
            try:
                if datetime.now(timezone.utc).date() > datetime.fromisoformat(gu).date():
                    print(f"[{sym}] watch SKIP — expired (good_until {gu})")
                    continue
            except ValueError:
                pass
        pick = {"action": "BUY", "instrument": "stock", "quantity": w.get("quantity"),
                "limit_price": w.get("limit_price") or w.get("trigger_price"),
                "take_profit": w.get("take_profit"), "stop_loss": w.get("stop_loss")}
        ok, why = validate_pick(pick)
        if not ok:
            print(f"[{sym}] watch SKIP — {why}")
            continue
        q = quote(client, sym)
        fired, reason = watch_triggered(w, q)
        if not fired:
            print(f"[{sym}] watching — {reason}")
            continue
        print(f"[{sym}] watch TRIGGER — {reason}")
        try_enter(client, acct, sym, pick["quantity"], float(pick["limit_price"]),
                  positions, blocked, bought, q=q,
                  tp=pick.get("take_profit"), sl=pick.get("stop_loss"))

    # B) FRESH BUY picks from orders.json.
    if not fresh:
        print("No fresh BUY picks.")
    else:
        for order in orders:
            if order.get("action") != "BUY":
                continue
            is_option = order.get("instrument") == "option"
            sym = order.get("underlying", "?") if is_option else order.get("symbol", "?")
            ok, why = validate_pick(order)
            if not ok:
                print(f"[{sym}] SKIP — {why}")
                continue
            if is_option:
                try_enter_option(client, acct, order, positions, blocked, bought)
            else:
                try_enter(client, acct, sym, order["quantity"], float(order["limit_price"]),
                          positions, blocked, bought,
                          tp=order.get("take_profit"), sl=order.get("stop_loss"))

    # ---- PAPER bookkeeping: mark-to-market, persist the book + running ledger ----
    # Reuse the marks pulled at the top; quote any names bought THIS run that aren't in it.
    if DRY_RUN and _PAPER is not None:
        for sym in list(_PAPER["positions"]):
            if sym not in marks:
                last = live_last(quote(client, sym))
                if last:
                    marks[sym] = last
        save_paper_account(_PAPER)
        write_paper_ledger(_PAPER, marks)

    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
